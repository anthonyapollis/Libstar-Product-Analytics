# Databricks notebook source
# MAGIC %md
# MAGIC # Exercise 1: payment gateway reconciliation (Delta Lake)
# MAGIC Uses the same two files and the same rules as the MySQL and dbt versions
# MAGIC (`exercise1-reconciliation/`). The last cells check that every result matches them.
# MAGIC
# MAGIC 1. **Load:** a `MERGE` on each file's natural key. The files are embedded below, so there
# MAGIC    is nothing to upload. Loading the same daily file again adds nothing.
# MAGIC 2. **Stage:** normalise the reference (upper-case, letters and digits only).
# MAGIC 3. **Match and categorise** every deposit and settlement → `recon_exceptions`.
# MAGIC 4. **Bridge** from the internal total to the gateway total → `recon_bridge`.
# MAGIC 5. **Checks** against the MySQL and dbt figures.

# COMMAND ----------

# MAGIC %run ./00_config

# COMMAND ----------

# MAGIC %md ## 1. Load the two files (idempotent MERGE)

# COMMAND ----------

import csv
import io
from decimal import Decimal
from datetime import datetime

INTERNAL_DEPOSITS_CSV = """__INTERNAL_DEPOSITS_CSV__"""
GATEWAY_SETTLEMENT_CSV = """__GATEWAY_SETTLEMENT_CSV__"""

ts = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
dep_rows = [(r["deposit_id"], r["player_id"], ts(r["created_at"]), Decimal(r["amount"]), r["currency"],
             r["method"], r["gateway_ref"], r["status"])
            for r in csv.DictReader(io.StringIO(INTERNAL_DEPOSITS_CSV.strip()))]
# row_id = position in the file: the settlement file has no unique key of its own
# (it contains genuine duplicates, which are one of the things this exercise must find).
gw_rows = [(i, r["gateway_txn_id"], r["merchant_ref"], ts(r["settled_at"]), Decimal(r["gross_amount"]),
            Decimal(r["fee"]), Decimal(r["net_amount"]), r["currency"], r["status"])
           for i, r in enumerate(csv.DictReader(io.StringIO(GATEWAY_SETTLEMENT_CSV.strip())), 1)]

spark.sql("""CREATE TABLE IF NOT EXISTS internal_deposits (
    deposit_id STRING NOT NULL, player_id STRING NOT NULL, created_at TIMESTAMP NOT NULL,
    amount DECIMAL(14,2) NOT NULL, currency STRING NOT NULL, method STRING NOT NULL,
    gateway_ref STRING NOT NULL, status STRING NOT NULL) USING DELTA""")
spark.sql("""CREATE TABLE IF NOT EXISTS gateway_settlement (
    row_id BIGINT NOT NULL, gateway_txn_id STRING NOT NULL, merchant_ref STRING NOT NULL,
    settled_at TIMESTAMP NOT NULL, gross_amount DECIMAL(14,2) NOT NULL, fee DECIMAL(14,2) NOT NULL,
    net_amount DECIMAL(14,2) NOT NULL, currency STRING NOT NULL, status STRING NOT NULL) USING DELTA""")

dep_schema = ("deposit_id STRING, player_id STRING, created_at TIMESTAMP, amount DECIMAL(14,2), "
              "currency STRING, method STRING, gateway_ref STRING, status STRING")
gw_schema = ("row_id BIGINT, gateway_txn_id STRING, merchant_ref STRING, settled_at TIMESTAMP, "
             "gross_amount DECIMAL(14,2), fee DECIMAL(14,2), net_amount DECIMAL(14,2), currency STRING, status STRING")


def load_files():
    spark.createDataFrame(dep_rows, dep_schema).createOrReplaceTempView("incoming_deposits")
    spark.createDataFrame(gw_rows, gw_schema).createOrReplaceTempView("incoming_settlements")
    # Natural keys: deposit_id; and (gateway_txn_id, settled_at) for settlements. A genuine
    # duplicate from the gateway differs in settled_at, so it is kept (it must be reported).
    spark.sql("""MERGE INTO internal_deposits t USING incoming_deposits s ON t.deposit_id = s.deposit_id
                 WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
    spark.sql("""MERGE INTO gateway_settlement t USING incoming_settlements s
                 ON t.gateway_txn_id = s.gateway_txn_id AND t.settled_at = s.settled_at
                 WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
    return (spark.table("internal_deposits").count(), spark.table("gateway_settlement").count())


first = load_files()
second = load_files()      # the same files again, as if a daily job re-ran
print("after first load:", first, " after loading the same files again:", second)
check(first == second == (326, 306), "326 deposits and 306 settlements; reloading adds no duplicates")

# COMMAND ----------

# MAGIC %md ## 2. Staging: normalised references

# COMMAND ----------

spark.sql("""CREATE OR REPLACE TEMP VIEW stg_internal_deposits AS
SELECT *, upper(regexp_replace(gateway_ref, '[^A-Za-z0-9]', '')) AS gateway_ref_norm FROM internal_deposits""")
spark.sql("""CREATE OR REPLACE TEMP VIEW stg_gateway_settlement AS
SELECT *, upper(regexp_replace(merchant_ref, '[^A-Za-z0-9]', '')) AS merchant_ref_norm FROM gateway_settlement""")
display(spark.sql("""SELECT 'internal_deposits' AS source, COUNT(*) AS row_count,
                            SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END) AS success_total
                     FROM internal_deposits
                     UNION ALL
                     SELECT 'gateway_settlement', COUNT(*), SUM(CASE WHEN status = 'SETTLED' THEN gross_amount ELSE 0 END)
                     FROM gateway_settlement"""))

# COMMAND ----------

# MAGIC %md ## 3. Match and categorise every row
# MAGIC The same rules as `dbt_jsb_assessment/models/marts/fct_recon_exceptions.sql`. Each row also gets
# MAGIC one of the brief's three classifications.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE TABLE recon_exceptions AS
WITH dep_dupe_flag AS (
    SELECT deposit_id, gateway_ref_norm, COUNT(*) OVER (PARTITION BY gateway_ref_norm) AS dep_ref_count
    FROM stg_internal_deposits WHERE status = 'SUCCESS'
),
gw_dupe_flag AS (
    SELECT row_id, merchant_ref_norm, COUNT(*) OVER (PARTITION BY merchant_ref_norm) AS gw_ref_count
    FROM stg_gateway_settlement
),
matched AS (
    SELECT d.deposit_id, d.player_id, d.created_at, d.amount AS dep_amount, d.gateway_ref, d.status AS dep_status,
           g.row_id AS settlement_row_id, g.gateway_txn_id, g.merchant_ref, g.settled_at,
           g.gross_amount, g.fee, g.net_amount, g.status AS gw_status, ddf.dep_ref_count, gdf.gw_ref_count
    FROM stg_internal_deposits d
    LEFT JOIN stg_gateway_settlement g ON g.merchant_ref_norm = d.gateway_ref_norm
    LEFT JOIN dep_dupe_flag ddf ON ddf.deposit_id = d.deposit_id
    LEFT JOIN gw_dupe_flag gdf ON gdf.row_id = g.row_id
    WHERE d.status = 'SUCCESS'
    UNION ALL
    -- settlement rows with no SUCCESS deposit: a FAILED deposit, or no internal record at all
    SELECT d2.deposit_id, d2.player_id, d2.created_at, d2.amount, g.merchant_ref, d2.status,
           g.row_id, g.gateway_txn_id, g.merchant_ref, g.settled_at,
           g.gross_amount, g.fee, g.net_amount, g.status, NULL, gdf.gw_ref_count
    FROM stg_gateway_settlement g
    LEFT JOIN gw_dupe_flag gdf ON gdf.row_id = g.row_id
    LEFT JOIN stg_internal_deposits d2 ON d2.gateway_ref_norm = g.merchant_ref_norm
    WHERE NOT EXISTS (SELECT 1 FROM stg_internal_deposits d
                      WHERE d.gateway_ref_norm = g.merchant_ref_norm AND d.status = 'SUCCESS')
),
categorised AS (
    SELECT deposit_id, player_id, created_at, dep_amount, gateway_ref, settlement_row_id, gateway_txn_id,
           merchant_ref, settled_at, gross_amount, fee, net_amount, gw_status,
           round(gross_amount * 0.02 + 1.00, 2) AS expected_fee,
           CASE
             WHEN dep_status = 'FAILED' AND gw_status = 'SETTLED' THEN 'BREAK: payment confirmed, wallet not credited'
             WHEN deposit_id IS NULL AND gw_status = 'SETTLED' AND settled_at < '2026-09-01 00:15:00'
               THEN 'TIMING: prior-period deposit settled at start of period'
             WHEN deposit_id IS NULL AND gw_status = 'SETTLED' THEN 'BREAK: unrecognised settlement (no internal record)'
             WHEN dep_ref_count > 1 THEN 'BREAK: duplicate internal SUCCESS deposit for one settlement (double-credit risk)'
             WHEN gw_ref_count > 1 THEN 'BREAK: duplicate gateway settlement for one reference (double-credit risk)'
             WHEN settlement_row_id IS NULL AND created_at >= '2026-09-07 23:45:00'
               THEN 'TIMING: settlement expected in next period (created near cut-off)'
             WHEN settlement_row_id IS NULL THEN 'BREAK: deposit SUCCESS, no gateway settlement found'
             WHEN gw_status = 'REVERSED' THEN 'REVERSAL: gateway reversed/charged back after settlement'
             WHEN abs(fee - round(gross_amount * 0.02 + 1.00, 2)) > 0.005 THEN 'BREAK: settled fee differs from contracted fee'
             WHEN abs(net_amount - (gross_amount - fee)) > 0.005 THEN 'BREAK: net amount is not gross minus fee'
             WHEN abs(dep_amount - gross_amount) > 0.015 THEN 'BREAK: settled gross amount differs from internal amount'
             WHEN abs(dep_amount - gross_amount) BETWEEN 0.005 AND 0.015 THEN 'NOT A PROBLEM: rounding difference <= 1 cent'
             ELSE 'OK: matched, amount and fee correct'
           END AS category,
           CASE
             WHEN dep_status = 'FAILED' AND gw_status = 'SETTLED' THEN gross_amount
             WHEN deposit_id IS NULL AND gw_status = 'SETTLED' THEN gross_amount
             WHEN settlement_row_id IS NULL THEN dep_amount
             WHEN gw_status = 'REVERSED' THEN gross_amount
             WHEN abs(fee - round(gross_amount * 0.02 + 1.00, 2)) > 0.005 THEN round(fee - round(gross_amount * 0.02 + 1.00, 2), 2)
             WHEN abs(net_amount - (gross_amount - fee)) > 0.005 THEN round((gross_amount - fee) - net_amount, 2)
             ELSE round(coalesce(dep_amount, 0) - coalesce(gross_amount, 0), 2)
           END AS financial_impact
    FROM matched
)
SELECT concat(coalesce(deposit_id, '-'), '|', coalesce(cast(settlement_row_id AS STRING), '-')) AS recon_key,
       categorised.*,
       substring_index(category, ':', 1) AS category_type,
       CASE substring_index(category, ':', 1)
         WHEN 'OK' THEN 'Matched' WHEN 'TIMING' THEN 'Timing difference'
         WHEN 'NOT A PROBLEM' THEN 'Not a problem' ELSE 'Genuine break' END AS classification
FROM categorised
""")
display(spark.sql("""SELECT classification, category, COUNT(*) AS rows, SUM(financial_impact) AS impact_nad
                     FROM recon_exceptions GROUP BY classification, category ORDER BY classification, rows DESC"""))

# COMMAND ----------

# MAGIC %md ## 4. The bridge: internal total → gateway total (gross amounts)

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE TABLE recon_bridge AS
WITH f AS (SELECT * FROM recon_exceptions),
dep_ranked AS (SELECT amount, row_number() OVER (PARTITION BY gateway_ref_norm ORDER BY deposit_id) AS rn
               FROM stg_internal_deposits WHERE status = 'SUCCESS'),
gw_ranked AS (SELECT gross_amount, row_number() OVER (PARTITION BY merchant_ref_norm ORDER BY row_id) AS rn
              FROM stg_gateway_settlement),
steps AS (
    SELECT 1 AS step_order, 'Internal SUCCESS deposits' AS step,
           (SELECT sum(amount) FROM stg_internal_deposits WHERE status = 'SUCCESS') AS amount
    UNION ALL SELECT 2, 'Duplicate internal deposits', -(SELECT coalesce(sum(amount), 0) FROM dep_ranked WHERE rn > 1)
    UNION ALL SELECT 3, 'Reversals', -(SELECT coalesce(sum(financial_impact), 0) FROM f WHERE category LIKE 'REVERSAL%')
    UNION ALL SELECT 4, 'Not yet settled', -(SELECT coalesce(sum(financial_impact), 0) FROM f
                                               WHERE category = 'BREAK: deposit SUCCESS, no gateway settlement found')
    UNION ALL SELECT 5, 'Settles next period (provisional)', -(SELECT coalesce(sum(financial_impact), 0) FROM f
                                               WHERE category LIKE 'TIMING: settlement expected%')
    UNION ALL SELECT 6, 'Prior-period deposits (provisional)', (SELECT coalesce(sum(financial_impact), 0) FROM f
                                               WHERE category LIKE 'TIMING: prior-period%')
    UNION ALL SELECT 7, 'Unrecognised settlements', (SELECT coalesce(sum(financial_impact), 0) FROM f WHERE category LIKE 'BREAK: unrecognised%')
    UNION ALL SELECT 8, 'Settled but marked FAILED', (SELECT coalesce(sum(financial_impact), 0) FROM f WHERE category LIKE 'BREAK: payment confirmed%')
    UNION ALL SELECT 9, 'Duplicate gateway rows', (SELECT coalesce(sum(gross_amount), 0) FROM gw_ranked WHERE rn > 1)
    UNION ALL SELECT 10, 'Gross amount differences', (SELECT coalesce(sum(gross_amount - dep_amount), 0) FROM f
                                               WHERE category = 'BREAK: settled gross amount differs from internal amount')
    UNION ALL SELECT 11, 'Rounding (1 cent)', (SELECT coalesce(sum(gross_amount - dep_amount), 0) FROM f WHERE category LIKE 'NOT A PROBLEM%')
)
SELECT step_order, step, round(amount, 2) AS amount,
       sum(round(amount, 2)) OVER (ORDER BY step_order) AS running_total
FROM steps
""")
display(spark.table("recon_bridge").orderBy("step_order"))

# COMMAND ----------

# MAGIC %md ## 5. Checks: the same results as MySQL and dbt

# COMMAND ----------

EXPECTED = __EXPECTED_BY_CATEGORY__   # category -> (rows, impact NAD), from the MySQL / dbt / pandas runs

got = {r["category"]: (r["n"], float(r["impact"])) for r in spark.sql(
    "SELECT category, COUNT(*) AS n, SUM(financial_impact) AS impact FROM recon_exceptions GROUP BY category").collect()}
for cat, (n, impact) in sorted(EXPECTED.items()):
    g = got.get(cat, (0, 0.0))
    check(g[0] == n and abs(g[1] - impact) < 0.005, f"{cat}: {n} rows, {impact:,.2f}")
check(set(got) == set(EXPECTED), "no unexpected categories")

gateway_total = spark.sql("SELECT sum(gross_amount) FROM gateway_settlement WHERE status = 'SETTLED'").first()[0]
bridge_end = spark.sql("SELECT sum(amount) FROM recon_bridge").first()[0]
print(f"bridge ends at {bridge_end:,.2f}; gateway SETTLED total {gateway_total:,.2f}")
check(bridge_end == gateway_total, "bridge residual is exactly 0.00")

dupes = spark.sql("SELECT COUNT(*) - COUNT(DISTINCT recon_key) FROM recon_exceptions").first()[0]
check(dupes == 0, "recon_key is unique (one row per deposit/settlement pair)")

# COMMAND ----------

# MAGIC %md ## Exceptions list (the brief's deliverable)
# MAGIC The matched rows are excluded. Row-by-row explanations are in `exercise1-reconciliation/exceptions.csv`.

# COMMAND ----------

display(spark.sql("""SELECT classification, category, deposit_id, gateway_txn_id, gateway_ref, merchant_ref,
                            dep_amount, gross_amount, fee, expected_fee, net_amount, financial_impact
                     FROM recon_exceptions WHERE category_type <> 'OK'
                     ORDER BY classification, category, coalesce(created_at, settled_at)"""))
