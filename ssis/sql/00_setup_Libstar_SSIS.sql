/*
================================================================================
LIBSTAR - SSIS (Biml) port of the ADF mapping data flow df_clean_products
================================================================================
Creates the on-premises SQL Server target the Biml-generated SSIS packages load.
Run once before generating packages: Biml reads external column metadata from
these tables at compile time.

Layers (same contract as the ADF version, different engine):
  stg.products_raw        every CSV field landed as text, untouched
  ref.*                   lookup-driven cleansing rules (replace ADF case() chains)
  stg.products_valid      typed, cleansed rows that passed every rule
  dq.products_quarantine  rows that failed a rule, kept as received + reject_reason
  dw.products_clean       de-duplicated publish table (latest date_added per product_id)
  etl.PackageRun          one row per package execution (managed-services audit trail)

Re-runnable.
================================================================================
*/
IF DB_ID('Libstar_SSIS') IS NULL CREATE DATABASE Libstar_SSIS;
GO
-- staging/warehouse loads are re-runnable from source, so point-in-time log backups are not needed
ALTER DATABASE Libstar_SSIS SET RECOVERY SIMPLE;
GO
USE Libstar_SSIS;
GO
IF SCHEMA_ID('etl') IS NULL EXEC('CREATE SCHEMA etl');
IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('ref') IS NULL EXEC('CREATE SCHEMA ref');
IF SCHEMA_ID('dq')  IS NULL EXEC('CREATE SCHEMA dq');
IF SCHEMA_ID('dw')  IS NULL EXEC('CREATE SCHEMA dw');
GO

/* ---------------- audit ---------------- */
IF OBJECT_ID('etl.PackageRun') IS NULL
CREATE TABLE etl.PackageRun (
    RunId          int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    PackageName    nvarchar(200)  NOT NULL,
    ExecutionGuid  nvarchar(50)   NULL,
    StartTime      datetime2(0)   NOT NULL DEFAULT SYSDATETIME(),
    EndTime        datetime2(0)   NULL,
    Status         varchar(20)    NOT NULL DEFAULT 'Running',
    RowsRead       bigint         NULL,
    RowsWritten    bigint         NULL,
    RowsRejected   bigint         NULL,
    Message        nvarchar(4000) NULL
);
GO

/* ---------------- environment config ----------------
   Folder locations differ per machine, so they live here rather than in the packages.
   run_ssis.ps1 -Configure writes this machine's paths. A non-empty package parameter wins. */
IF OBJECT_ID('etl.Config') IS NULL
CREATE TABLE etl.Config (
    ConfigKey   varchar(50)    NOT NULL PRIMARY KEY,
    ConfigValue nvarchar(400)  NOT NULL,
    UpdatedAt   datetime2(0)   NOT NULL DEFAULT SYSDATETIME()
);
GO

/* ---------------- staging (raw, all text) ---------------- */
DROP TABLE IF EXISTS stg.products_raw;
CREATE TABLE stg.products_raw (
    raw_product_id     nvarchar(255) NULL,
    raw_sku            nvarchar(255) NULL,
    raw_product_name   nvarchar(255) NULL,
    raw_category       nvarchar(255) NULL,
    raw_brand          nvarchar(255) NULL,
    raw_sales_channel  nvarchar(255) NULL,
    raw_province       nvarchar(255) NULL,
    raw_price_zar      nvarchar(255) NULL,
    raw_cost_zar       nvarchar(255) NULL,
    raw_weight_kg      nvarchar(255) NULL,
    raw_stock_qty      nvarchar(255) NULL,
    raw_units_sold_12m nvarchar(255) NULL,
    raw_date_added     nvarchar(255) NULL,
    raw_is_active      nvarchar(255) NULL,
    raw_rating         nvarchar(255) NULL,
    source_file        nvarchar(260) NULL,
    load_run_id        int           NULL
);
GO

/* ---------------- reference / rule tables ---------------- */
DROP TABLE IF EXISTS ref.brand_map;
CREATE TABLE ref.brand_map (
    bm_brand_key        nvarchar(100) NOT NULL PRIMARY KEY,
    bm_brand            nvarchar(100) NOT NULL,
    bm_brand_solution   nvarchar(100) NOT NULL,
    bm_primary_category nvarchar(50)  NOT NULL,
    bm_product_group    nvarchar(50)  NOT NULL
);   -- loaded from data/reference/brand_map.csv by LIB_00_LoadReference

DROP TABLE IF EXISTS ref.province_map;
CREATE TABLE ref.province_map (match_key nvarchar(50) NOT NULL PRIMARY KEY, province nvarchar(50) NOT NULL);
INSERT INTO ref.province_map VALUES
 (N'western cape',N'Western Cape'),(N'wc',N'Western Cape'),
 (N'gauteng',N'Gauteng'),(N'gp',N'Gauteng'),
 (N'kwazulu-natal',N'KwaZulu-Natal'),(N'kzn',N'KwaZulu-Natal'),
 (N'eastern cape',N'Eastern Cape'),(N'ec',N'Eastern Cape'),
 (N'mpumalanga',N'Mpumalanga'),(N'mp',N'Mpumalanga'),
 (N'limpopo',N'Limpopo'),(N'lp',N'Limpopo'),
 (N'north west',N'North West'),(N'nw',N'North West'),
 (N'free state',N'Free State'),(N'fs',N'Free State'),
 (N'northern cape',N'Northern Cape'),(N'nc',N'Northern Cape');

DROP TABLE IF EXISTS ref.channel_map;
CREATE TABLE ref.channel_map (match_key nvarchar(100) NOT NULL PRIMARY KEY, sales_channel nvarchar(100) NOT NULL);
INSERT INTO ref.channel_map VALUES
 (N'retail and wholesale',N'Retail and wholesale'),
 (N'food service',N'Food service'),
 (N'industrial and contract manufacturing',N'Industrial and contract manufacturing'),
 (N'export',N'Export');

DROP TABLE IF EXISTS ref.category_map;
CREATE TABLE ref.category_map (match_key nvarchar(50) NOT NULL PRIMARY KEY, category nvarchar(50) NOT NULL, product_group nvarchar(50) NOT NULL);
INSERT INTO ref.category_map VALUES
 (N'dairy',N'Dairy',N'Perishable products'),
 (N'convenience meals',N'Convenience Meals',N'Perishable products'),
 (N'value-added meats',N'Value-added Meats',N'Perishable products'),
 (N'baby',N'Baby',N'Perishable products'),
 (N'fresh mushrooms',N'Fresh Mushrooms',N'Perishable products'),
 (N'dry condiments',N'Dry condiments',N'Ambient products'),
 (N'wet condiments',N'Wet condiments',N'Ambient products'),
 (N'meal ingredients',N'Meal ingredients',N'Ambient products'),
 (N'baking',N'Baking',N'Ambient products'),
 (N'snacking',N'Snacking',N'Ambient products'),
 (N'spreads',N'Spreads',N'Ambient products'),
 (N'beverages',N'Beverages',N'Ambient products');
GO

/* ---------------- typed outputs ---------------- */
DROP TABLE IF EXISTS stg.products_valid;
CREATE TABLE stg.products_valid (
    product_id      nvarchar(50)  NOT NULL,
    sku             nvarchar(50)  NULL,
    product_name    nvarchar(255) NULL,
    product_group   nvarchar(50)  NULL,
    category        nvarchar(50)  NULL,
    brand           nvarchar(100) NULL,
    brand_solution  nvarchar(100) NULL,
    sales_channel   nvarchar(100) NULL,
    province        nvarchar(50)  NULL,
    price_zar       float         NULL,
    cost_zar        float         NULL,
    margin_pct      float         NULL,
    weight_kg       float         NULL,
    stock_qty       int           NULL,
    units_sold_12m  int           NULL,
    revenue_12m_zar float         NULL,
    date_added      date          NULL,
    is_active       bit           NULL,
    rating          float         NULL,
    load_run_id     int           NULL
);

DROP TABLE IF EXISTS dq.products_quarantine;
CREATE TABLE dq.products_quarantine (
    raw_product_id     nvarchar(255) NULL,
    raw_sku            nvarchar(255) NULL,
    raw_product_name   nvarchar(255) NULL,
    raw_category       nvarchar(255) NULL,
    raw_brand          nvarchar(255) NULL,
    raw_sales_channel  nvarchar(255) NULL,
    raw_province       nvarchar(255) NULL,
    raw_price_zar      nvarchar(255) NULL,
    raw_cost_zar       nvarchar(255) NULL,
    raw_weight_kg      nvarchar(255) NULL,
    raw_stock_qty      nvarchar(255) NULL,
    raw_units_sold_12m nvarchar(255) NULL,
    raw_date_added     nvarchar(255) NULL,
    raw_is_active      nvarchar(255) NULL,
    raw_rating         nvarchar(255) NULL,
    reject_reason      nvarchar(100) NOT NULL,
    load_run_id        int           NULL
);

DROP TABLE IF EXISTS dw.products_clean;
CREATE TABLE dw.products_clean (
    product_id      nvarchar(50)  NOT NULL PRIMARY KEY,
    sku             nvarchar(50)  NULL,
    product_name    nvarchar(255) NULL,
    product_group   nvarchar(50)  NULL,
    category        nvarchar(50)  NULL,
    brand           nvarchar(100) NULL,
    brand_solution  nvarchar(100) NULL,
    sales_channel   nvarchar(100) NULL,
    province        nvarchar(50)  NULL,
    price_zar       float         NULL,
    cost_zar        float         NULL,
    margin_pct      float         NULL,
    weight_kg       float         NULL,
    stock_qty       int           NULL,
    units_sold_12m  int           NULL,
    revenue_12m_zar float         NULL,
    date_added      date          NULL,
    is_active       bit           NULL,
    rating          float         NULL,
    load_run_id     int           NULL
);
GO

/* ---------------- reconciliation views ---------------- */
CREATE OR ALTER VIEW dq.vw_reject_summary AS
SELECT reject_reason, COUNT_BIG(*) AS row_count
FROM dq.products_quarantine
GROUP BY reject_reason;
GO
CREATE OR ALTER VIEW dw.vw_kpi_summary AS
SELECT
    COUNT_BIG(*)                                        AS total_skus,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END)      AS active_skus,
    CAST(SUM(revenue_12m_zar) AS decimal(18,2))         AS revenue_12m_zar,
    CAST(AVG(margin_pct) AS decimal(9,2))               AS avg_margin_pct,
    CAST(AVG(price_zar) AS decimal(9,2))                AS avg_price_zar,
    CAST(AVG(rating) AS decimal(4,2))                   AS avg_rating,
    SUM(CAST(stock_qty AS bigint))                      AS total_stock_units,
    (SELECT COUNT_BIG(*) FROM dq.products_quarantine)   AS quarantined_rows,
    (SELECT COUNT_BIG(*) FROM stg.products_valid) - COUNT_BIG(*) AS duplicate_rows_removed,
    (SELECT COUNT_BIG(*) FROM stg.products_raw)         AS raw_rows
FROM dw.products_clean;
GO
