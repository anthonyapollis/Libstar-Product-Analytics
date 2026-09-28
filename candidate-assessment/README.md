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
| 1. Reconciliation | 294/306 (96%) of gateway settlements match exactly. The bridge from the internal total (R218,280.00) to the gateway total (R217,979.97) reconciles to **R0.00 unexplained** across 11 categorised exception types. | `exercise1-reconciliation/summary.md`, `exceptions.csv` |
| 2. API ingestion | Killed mid-page with SIGKILL, restarted, completed with 0 duplicates/0 missing rows; handled a live 429 automatically; correctly quarantined 1 bad record instead of dropping it; picked up 40 changed + 25 new records after a simulated provider update. | `exercise2-ingestion/evidence/run_transcript.txt` |
| 3. Schema design | 23-table MySQL schema (players/PII separated, append-only wallet ledger, one bet header + per-product detail tables, SCD2 history, event-sourced bonus rollover). DDL runs clean; all 4 required queries return correct results against seed data. | `exercise3-schema-design/erd.png`, `design_notes.md` |
| dbt | One project spanning all three exercises: Exercise 3's star schema (`dim_player`, `fact_bet`, `fact_wallet_transaction`, `fact_bonus_transaction`, ...) **and** Exercise 1's reconciliation as a scheduled model (`fct_recon_exceptions`) with singular tests enforcing the R0.00 bridge, full source coverage and wallet-cache = ledger — `dbt build`: **61/61 pass, 0 errors**. | `dbt_jsb_assessment/evidence/dbt_build_output.txt` |
| Power BI | A Power BI project (`JSB_Assessment.pbip`) built on the dbt marts: 7-table star schema, 10 DAX measures, 2 report pages, loading from CSV. Generated and validated by script, with expected values for every visual. | `powerbi/README.md`, `powerbi/expected_values.md` |
| Write-up | The full submission as one document, with screenshots of every key step: `JSB_Candidate_Submission.docx` (and `.pdf`). | this folder |

## Tools used
MySQL 8.0 and MariaDB 10.11 (all SQL verified on both) · Python 3.11 (stdlib `urllib`, `pymysql`,
`pandas` for analysis only) · dbt-core 1.7 + dbt-mysql · Postman / Newman · Mermaid for the ERD ·
Power BI (`.pbip` project).
