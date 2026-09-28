# Load this submission into your local MySQL / MariaDB (XAMPP)

Two scripts, run once, in order. Both were tested on MariaDB 10.11.

| Step | Script | What it does |
|---|---|---|
| 1 | `00_drop_other_build_tables.sql` | Drops the 45 tables and views another build left in `jsb_assessment` (`affiliate`, `api_transactions`, `fct_reconciliation`, ...). It drops only those listed names, so any other table is left alone. |
| 2 | `01_load_submission_tables.sql` | Creates `jsb_assessment` (Exercises 1 and 2, 6 tables) and `jsb_platform` (Exercise 3, 23 tables), and loads the exact rows every figure in the submission was computed from. **Re-running drops and reloads these 29 tables, so any later changes to them are lost.** It never touches tables it didn't create. |

**MySQL Workbench:** File → Open SQL Script → pick the file → Execute (lightning bolt). Do step 1, then step 2.

**Command line (XAMPP):**
```bat
C:\xampp\mysql\bin\mysql.exe -u root < 00_drop_other_build_tables.sql
C:\xampp\mysql\bin\mysql.exe -u root < 01_load_submission_tables.sql
```

Step 2 ends by printing row counts. You should see:

| Table | Rows |
|---|---|
| internal_deposits | 326 |
| gateway_settlement | 306 |
| transactions | 1,024 |
| ingest_runs | 3 |
| ingest_rejects | 1 |
| jsb_platform tables | 23 |

## Then, optionally
- **Reconciliation:** run `exercise1-reconciliation/sql/03_reconciliation.sql`. It shows 274 exact matches and the bridge.
- **dbt:** `cd dbt_jsb_assessment`, set your connection in `profiles.yml`, then run `dbt build`. It builds `jsb_platform_staging` (views) and `jsb_platform_marts` (tables).

`build_load_sql.py` regenerates `01_load_submission_tables.sql` from the source files.
