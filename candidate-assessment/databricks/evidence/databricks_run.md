# Run on Databricks

- **Date (UTC):** 2026-09-28, 23:13:08 to 23:21:48
- **Host:** https://dbc-ea48b979-9753.cloud.databricks.com (Databricks Free Edition, serverless compute, catalog `workspace`)
- **Notebook folder:** `/Users/anthony.apollis@gmail.com/JSB_Assessment`:
  https://dbc-ea48b979-9753.cloud.databricks.com/browse/folders/1997667018168060?o=7474649344710062
- **Job run** "JSB assessment - all exercises" (one run, three notebook tasks, ex1 → ex2 → ex3):
  https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/308746372139777/run/460654207301296
  **Result: SUCCESS**

| Task | Notebook | Result | Checks | Task run |
|---|---|---|---|---|
| ex1 | `01_exercise1_reconciliation` | SUCCESS | 17 / 17 PASS | https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/308746372139777/run/453545434689160 |
| ex2 | `02_exercise2_incremental_ingestion` | SUCCESS | 6 / 6 PASS | https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/308746372139777/run/340425981901042 |
| ex3 | `03_exercise3_schema` | SUCCESS | 9 / 9 PASS | https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/308746372139777/run/685793852884612 |

All 32 checks passed. This is the same total as the local run in `local_test_run.txt`.

## Fixes needed on Databricks
The local test runs on open-source Spark, so it couldn't surface these two issues. Both fixes are in
the templates, and the notebooks were rebuilt with `build_notebooks.py`. No check was changed or removed.

1. **Exercise 2: the mock API couldn't be reached** (`network_error_exhausted`, `Connection refused`).
   Serverless compute refuses TCP connections to `127.0.0.1`. It also refuses connections to a fixed
   port such as 8765, even on the compute's own address. Diagnostic runs on this workspace confirmed
   that a server bound to `0.0.0.0` on an OS-assigned port, called through the compute's host name,
   is reachable, and stays reachable in later cells. On Databricks the notebook now serves the mock that
   way (`src/02_exercise2_incremental_ingestion.py`). Local runs still use `127.0.0.1:8765`. The retry and
   validation code copied from `ingest.py` is unchanged.
2. **Exercise 3: the generated column was rejected** (`UNSUPPORTED_EXPRESSION_GENERATED_COLUMN`).
   `stake_real_amount + stake_bonus_amount` is `DECIMAL(19,4)` in Spark, but the column is
   `DECIMAL(18,4)`, and Delta requires the two types to match. The DDL translator
   (`build_notebooks.py`) now wraps every generated expression in `CAST(... AS <column type>)`.
   The local test drops generated columns, so it behaves the same as before.

Earlier attempts before these fixes: job runs 821057838861563, 975811174562656 and 599905094907304
(ex2 failed), and 1117060907725171 (ex3 failed). The three diagnostic runs ran from a temporary
notebook, which was deleted afterwards.
