-- Run against the SERVERLESS endpoint, database: libstar
-- Creates external access + reporting views consumed by Qlik Sense,
-- the ebook charts and the Excel report (single source of truth).

IF NOT EXISTS (SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = '$(MASTER_KEY_PWD)';
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_scoped_credentials WHERE name = 'msi_cred')
    CREATE DATABASE SCOPED CREDENTIAL msi_cred WITH IDENTITY = 'Managed Identity';
GO

IF NOT EXISTS (SELECT 1 FROM sys.external_data_sources WHERE name = 'curated')
    CREATE EXTERNAL DATA SOURCE curated
    WITH (LOCATION = 'https://stpargoparcels01.dfs.core.windows.net/curated', CREDENTIAL = msi_cred);
GO

IF SCHEMA_ID('rpt') IS NULL EXEC('CREATE SCHEMA rpt');
GO

CREATE OR ALTER VIEW rpt.vw_products AS
SELECT *
FROM OPENROWSET(
    BULK 'products_clean/*.parquet',
    DATA_SOURCE = 'curated',
    FORMAT = 'PARQUET'
) AS p;
GO

CREATE OR ALTER VIEW rpt.vw_quarantine AS
SELECT *
FROM OPENROWSET(
    BULK 'products_quarantine/*.parquet',
    DATA_SOURCE = 'curated',
    FORMAT = 'PARQUET'
) AS q;
GO

CREATE OR ALTER VIEW rpt.vw_kpi_summary AS
SELECT
    COUNT_BIG(*)                                   AS total_skus,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_skus,
    CAST(SUM(revenue_12m_zar) AS DECIMAL(18, 2))   AS revenue_12m_zar,
    CAST(AVG(margin_pct) AS DECIMAL(9, 2))         AS avg_margin_pct,
    CAST(AVG(price_zar) AS DECIMAL(9, 2))          AS avg_price_zar,
    CAST(AVG(rating) AS DECIMAL(4, 2))             AS avg_rating,
    SUM(CAST(stock_qty AS BIGINT))                 AS total_stock_units
FROM rpt.vw_products;
GO

CREATE OR ALTER VIEW rpt.vw_category_performance AS
SELECT
    product_group,
    category,
    COUNT_BIG(*)                                 AS sku_count,
    CAST(SUM(revenue_12m_zar) AS DECIMAL(18, 2)) AS revenue_12m_zar,
    CAST(AVG(margin_pct) AS DECIMAL(9, 2))       AS avg_margin_pct,
    CAST(AVG(price_zar) AS DECIMAL(9, 2))        AS avg_price_zar,
    CAST(AVG(rating) AS DECIMAL(4, 2))           AS avg_rating
FROM rpt.vw_products
GROUP BY product_group, category;
GO

CREATE OR ALTER VIEW rpt.vw_brand_performance AS
SELECT
    brand_solution,
    brand,
    COUNT_BIG(*)                                 AS sku_count,
    CAST(SUM(revenue_12m_zar) AS DECIMAL(18, 2)) AS revenue_12m_zar,
    CAST(AVG(margin_pct) AS DECIMAL(9, 2))       AS avg_margin_pct,
    CAST(AVG(rating) AS DECIMAL(4, 2))           AS avg_rating
FROM rpt.vw_products
GROUP BY brand_solution, brand;
GO

CREATE OR ALTER VIEW rpt.vw_province_performance AS
SELECT
    province,
    COUNT_BIG(*)                                 AS sku_count,
    CAST(SUM(revenue_12m_zar) AS DECIMAL(18, 2)) AS revenue_12m_zar,
    CAST(AVG(margin_pct) AS DECIMAL(9, 2))       AS avg_margin_pct
FROM rpt.vw_products
GROUP BY province;
GO

CREATE OR ALTER VIEW rpt.vw_channel_performance AS
SELECT
    sales_channel,
    COUNT_BIG(*)                                 AS sku_count,
    CAST(SUM(revenue_12m_zar) AS DECIMAL(18, 2)) AS revenue_12m_zar,
    CAST(AVG(margin_pct) AS DECIMAL(9, 2))       AS avg_margin_pct
FROM rpt.vw_products
GROUP BY sales_channel;
GO

CREATE OR ALTER VIEW rpt.vw_data_quality AS
SELECT reject_reason, COUNT_BIG(*) AS row_count
FROM rpt.vw_quarantine
GROUP BY reject_reason;
GO

-- ML anomaly scores (uploaded from ml/outputs after model training)
IF EXISTS (SELECT 1 FROM sys.external_data_sources WHERE name = 'curated')
    EXEC('CREATE OR ALTER VIEW rpt.vw_ml_anomalies AS
    SELECT *
    FROM OPENROWSET(
        BULK ''ml_anomalies/*.parquet'',
        DATA_SOURCE = ''curated'',
        FORMAT = ''PARQUET''
    ) AS a');
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'qlik_reader')
    CREATE USER qlik_reader FOR LOGIN qlik_reader;
GO

GRANT SELECT ON SCHEMA::rpt TO qlik_reader;
GRANT REFERENCES ON DATABASE SCOPED CREDENTIAL::msi_cred TO qlik_reader;
GO
