# Set the project up on your local XAMPP MariaDB, and watch dbt build it

## Quick start
Double-click **`setup_local.bat`** with XAMPP's MySQL running. It pauses after each step so you
can look at the result in Workbench.

| Step | What runs | What you'll see in Workbench |
|---|---|---|
| 1 | `01_load_submission_tables.sql`, the source data | `jsb_assessment` (6 tables), `jsb_platform` (23 tables) |
| 2 | Installs dbt 1.7 in a private Python environment (`local_load\.dbt-venv`, first run only) | nothing yet |
| 3 | `dbt debug --target xampp`: checks dbt can connect | nothing yet |
| 4 | `dbt run --select staging`: builds 11 views | `jsb_platform_staging` |
| 5 | `dbt run --select marts`: builds 12 tables | `jsb_platform_marts` |
| 6 | `dbt test`: runs 44 tests | nothing new; all should say PASS |

What each table is for, and why dbt adds 23 objects on top of the 29 base tables, is in
`../TABLE_INVENTORY.md`.

**Requirements:**
- XAMPP MySQL/MariaDB on port 3306, user `root` with no password (the XAMPP default).
- Python 3.9 to 3.11. dbt 1.7 doesn't support newer Pythons; if the install fails, install 3.11
  from python.org.
- If your `mysql.exe` isn't under `C:\xampp`, set it first:
  `set XAMPP_MYSQL=C:\path\to\mysql\bin\mysql.exe`.

## How dbt works here, in five points
1. **`profiles.yml` says where the database is.** The `xampp` target points at your local server.
   The `dev` target is the one used in the build container.
2. **Each model is one `SELECT` in a `.sql` file** under `dbt_jsb_assessment/models/`. dbt wraps it
   in `CREATE VIEW` or `CREATE TABLE`, as `dbt_project.yml` says. Staging models are views; marts
   are tables.
3. **Models refer to each other with `{{ ref('stg_bets') }}`, and to raw tables with
   `{{ source('jsb_platform', 'bets') }}`.** From those references dbt works out the build order:
   staging first, then the marts that read them.
4. **To see the actual SQL dbt sent to the database**, look in
   `dbt_jsb_assessment/target/run/jsb_assessment/models/...` after a run.
5. **Tests are queries that must return no rows.** They're declared in `models/*/_*.yml` (unique,
   not null, accepted values) or written in `tests/*.sql`. Examples: the bridge must reconcile to 0,
   and the wallet balance cache must equal the ledger.

## Useful commands
Run these from `dbt_jsb_assessment`, after `set DBT_PROFILES_DIR=.`:

```bat
..\local_load\.dbt-venv\Scripts\dbt build --target xampp
..\local_load\.dbt-venv\Scripts\dbt run --select fct_recon_exceptions --target xampp
..\local_load\.dbt-venv\Scripts\dbt run --select +mart_recon_bridge --target xampp
..\local_load\.dbt-venv\Scripts\dbt test --select fct_recon_exceptions --target xampp
..\local_load\.dbt-venv\Scripts\dbt ls --target xampp
```

They do the following, in order:
1. Build and test everything.
2. Rebuild one model.
3. Rebuild a model and everything it depends on.
4. Run the tests on one model.
5. List every model and test.

## Only the source data, without dbt
Workbench → File → Open SQL Script → `01_load_submission_tables.sql` → Execute. It prints row
counts at the end: 326 deposits, 306 settlements, 1,024 transactions, 3 runs, 1 reject, and 23
`jsb_platform` tables.

**Re-running resets the 29 base tables** to the submission data, so any later changes to them are
lost. It never touches other tables.

## History
The old builds were removed from the local server by Codex on 2026-09-28, after a full backup (see
`../CODEX_REVIEW.md`). `00_drop_other_build_tables.sql` is withdrawn and does nothing.

## If MySQL Workbench closes while running the script
Workbench doesn't officially support MariaDB and quits on large scripts, even split into parts.
Use Workbench only to look at the tables afterwards, and load the script in one of these ways:
- **phpMyAdmin (point and click, part of XAMPP).**
  1. Start Apache and MySQL in the XAMPP Control Panel.
  2. Open http://localhost/phpmyadmin and click the **Import** tab, without selecting a database.
  3. Choose `01_load_submission_tables.sql`, then click **Import**.
- **Run it from the command line instead.** MySQL Workbench doesn't officially support MariaDB
  (the "Warning – not supported" on its tab) and can crash on a large script. `setup_local.bat`
  uses XAMPP's `mysql.exe` instead. You can also run the script directly:
  `C:\xampp\mysql\bin\mysql.exe -u root < 01_load_submission_tables.sql`
- **Or run it in three smaller parts, in this order:** `01a_exercise1.sql`, `01b_exercise2.sql`,
  `01c_exercise3.sql`. The result is the same, and if something closes you'll know which part
  caused it.
- **If the XAMPP MySQL server stops** (red in the XAMPP Control Panel), the reason is in
  `C:\xampp\mysql\data\mysql_error.log`. The last 20 lines are what's needed to fix it.
