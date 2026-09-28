# JSB Data Engineer — Practical Exercises

All three exercises, built and verified end-to-end: MySQL 8.0 for every schema/query, Python for the
reconciliation load and the ingestion program, Postman/Newman for the API contract, and dbt for the
reporting layer. Everything under this folder ran successfully in this environment — see each
exercise's `evidence/`/`screenshots/` folder for captured output.

> **A note on screenshots:** this was built in a headless cloud container with no GUI, so
> "screenshots" here are rendered captures of the actual terminal output of each run (not staged) —
> clearly labelled as such rather than pretending otherwise. Every number in them is real, reproducible
> by re-running the commands in each exercise's README.

## Layout
```
exercise1-reconciliation/   Payment gateway reconciliation (MySQL + Python)
exercise2-ingestion/        Incremental, restartable API ingestion (Python + MySQL + Postman)
exercise3-schema-design/    Database design: players, wallets, bets, bonuses (MySQL + ERD)
dbt_jsb_assessment/         dbt reporting layer (staging + marts) built on Exercise 3's schema
powerbi/                    Power BI project (.pbip) on the dbt marts, data embedded
local_load/                 Two SQL scripts: clean up and load all 30 tables into a local MySQL/MariaDB
```

## Quickstart (reproduce everything)
```bash
# Exercise 1
mysql -u <user> -p < exercise1-reconciliation/sql/01_schema.sql
python exercise1-reconciliation/sql/02_load.py
mysql -u <user> -p jsb_assessment < exercise1-reconciliation/sql/03_reconciliation.sql

# Exercise 2
mysql -u <user> -p < exercise2-ingestion/schema.sql
python exercise2-ingestion/mock_api.py &
python exercise2-ingestion/ingest.py
newman run exercise2-ingestion/postman/JSB_Assessment_Exercise2.postman_collection.json

# Exercise 3
mysql -u <user> -p < exercise3-schema-design/ddl.sql
mysql -u <user> -p jsb_platform < exercise3-schema-design/seed.sql
mysql -u <user> -p jsb_platform < exercise3-schema-design/example_queries.sql

# dbt reporting layer (needs Exercise 3's schema + seed loaded first)
cd dbt_jsb_assessment && export DBT_PROFILES_DIR=. && dbt build
```

## What's in each exercise
| Exercise | Bottom line | Key evidence |
|---|---|---|
| 1. Reconciliation | 274 of 306 settlements (90%) match exactly on reference, amount, fee and net. The rest fall into 12 exception types, and the bridge from the internal total (R218,280.00) to the gateway total (R217,979.97) reconciles to **R0.00 unexplained**. Every row was cross-checked by a second, independent implementation. | `exercise1-reconciliation/summary.md`, `exceptions.csv` |
| 2. API ingestion | Killed mid-page with SIGKILL, restarted, completed with 0 duplicates/0 missing rows; handled a live 429 automatically; correctly quarantined 1 bad record instead of dropping it; picked up 40 changed + 25 new records after a simulated provider update. | `exercise2-ingestion/evidence/run_transcript.txt` |
| 3. Schema design | 24-table schema: personal data separated, append-only wallet ledger moved only by idempotent, locking posting procedures, one bet header + per-product detail tables, SCD2 history (VIP, tags, status/KYC), event-sourced bonus rollover, 39 CHECK constraints. All 4 required queries answered from seed data; the posting test proves replay, reversal and concurrency. | `exercise3-schema-design/erd.png`, `design_notes.md` |
| dbt | One project spanning all three exercises: Exercise 3's star schema (`dim_player`, `fact_bet`, `fact_wallet_transaction`, `fact_bonus_transaction`, ...) **and** Exercise 1's reconciliation as a scheduled model (`fct_recon_exceptions`) plus the bridge as its own mart (`mart_recon_bridge`) and Exercise 2's run log (`stg_ingest_runs`), with singular tests enforcing the R0.00 bridge, full source coverage and wallet-cache = ledger — `dbt build`: **78/78 pass (24 models, 54 tests), 0 errors**. Every mart has a primary key; the ledger and API facts load incrementally. | `dbt_jsb_assessment/evidence/dbt_build_output.txt` |
| Power BI | A Power BI project (`JSB_Assessment.pbip`) built on the dbt marts and covering all three exercises: 11 tables, 7 relationships, 28 DAX measures (22 calculations, 6 tile-colour rules), 4 report pages (NGR overview, player balances, reconciliation waterfall, ingestion monitoring). Data is embedded, so it opens and refreshes with no path to set. Generated and validated by script, with expected values for every visual. | `powerbi/README.md`, `powerbi/expected_values.md` |
| Local database | `local_load/setup_local.bat` loads the 30 base tables into a local XAMPP MariaDB and runs dbt step by step (11 views, 13 tables, 54 tests). Every table is explained in `TABLE_INVENTORY.md`. | `local_load/README.md`, `TABLE_INVENTORY.md` |
| Databricks | The same three exercises as Databricks notebooks on Delta Lake, built from the same files. 31 checks reproduce the MySQL/dbt results; tested locally on Spark 4 + Delta 4. | `databricks/README.md` |
| Write-up | The full submission as one document, with screenshots of every key step: `JSB_Candidate_Submission.docx` (and `.pdf`). | this folder |

## Tools used
MySQL 8.0 and MariaDB 10.11 (all SQL verified on both) · Python 3.11 (stdlib `urllib`, `pymysql`,
`pandas` for analysis only) · dbt-core 1.7 + dbt-mysql · Postman / Newman · Mermaid for the ERD ·
Power BI (`.pbip` project).
