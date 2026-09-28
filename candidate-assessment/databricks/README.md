# The three exercises on Databricks (Delta Lake, Unity Catalog)

The same data and the same rules as the MySQL/dbt build, as four Databricks notebooks. Each
notebook ends with checks that fail loudly if a result differs from the MySQL/dbt figures.

| Notebook | What it does | Checks |
|---|---|---|
| `00_config` | Catalog `workspace`, schema `jsb_assessment`, UTC. Every other notebook runs it first | |
| `01_exercise1_reconciliation` | Loads both files with an idempotent `MERGE` (loaded twice to prove no duplicates), then categorises every row and builds the bridge | 17 checks: every category's rows and rand value equal MySQL/dbt; the bridge residual is exactly 0.00 |
| `02_exercise2_incremental_ingestion` | Runs the supplied mock API inside the notebook and loads it into Delta with `MERGE`. Crashes on purpose between writing a page and moving its checkpoint, then restarts, reruns, calls `/admin/advance` and reruns | The table matches the API id by id after the restart and after the new activity; exactly 25 new and 40 changed; the crashed run is ABANDONED; one reject |
| `03_exercise3_schema` | The 23 tables in Delta, CHECK constraints (enforced), primary and foreign keys (declared in Unity Catalog), the seed data and the four queries | A negative stake is refused; no duplicate on any of 42 keys; no orphan on any of 30 foreign keys; the four query answers; wallet cache = ledger |

## Import and run (Databricks Free Edition)
1. Download `JSB_Databricks_Notebooks.zip`.
2. **Import it.**
   1. In Databricks, click **Workspace**, then open your user folder (**Home**).
   2. Click the **⋮** menu (top right), then **Import**, then **File**.
   3. Drop in the zip and click **Import**.

   This creates a folder, `JSB_Assessment`, with the four notebooks. If your workspace doesn't unpack
   the zip, extract it on your PC and import the four `.py` files one at a time; each is a notebook.
3. **Run the notebooks.** Open `01_exercise1_reconciliation`, click **Connect** (top right), choose
   **Serverless**, then click **Run all**. Then run `02_…`, then `03_…`. Each takes 1–3 minutes.
   Every check prints `PASS: …`.
4. **See the tables** under **Catalog → workspace → jsb_assessment**.

**To run it on a schedule:** under **Jobs & Pipelines → Create job**, add the notebooks as tasks,
and set **Maximum concurrent runs = 1**. That setting is the Databricks equivalent of the MySQL
version's lock: two ingestion runs never overlap. In production, the Exercise 2 task would call
`run_once()` only, not the demo reset.

## How MySQL maps to Databricks here
| MySQL (this project) | Databricks |
|---|---|
| One transaction per page (rows + rejects + checkpoint) | Delta commits one table at a time, so writes are ordered (data → rejects → checkpoint → counters) and each is an idempotent `MERGE`. A crash re-reads at most one page, and re-applying it changes nothing |
| `GET_LOCK` | The Job's **Maximum concurrent runs = 1** |
| `PRIMARY KEY`, `UNIQUE`, `FOREIGN KEY` enforced | Primary and foreign keys are declared but **not enforced**; `UNIQUE` doesn't exist. So loads `MERGE` on the key, and the notebooks **check** every key for duplicates and every foreign key for orphans |
| `ENUM`, `CHECK`, `NOT NULL` | `CHECK` and `NOT NULL`, enforced by Delta (the notebook demonstrates it) |
| `AUTO_INCREMENT`, generated column, `DEFAULT` | Identity column, generated column, column defaults |
| Indexes | None in Delta. The two large tables use liquid clustering (`CLUSTER BY`) |

## How it was tested, and the limit of that
`run_local.py` runs the notebooks with open-source Spark 4 and Delta Lake 4. All 31 checks pass
(`evidence/local_test_run.txt`).

A few features exist only on Databricks, so they couldn't be run here:
- Unity Catalog primary and foreign keys;
- identity and generated columns;
- `USE CATALOG`.

The local test skips those statements; the notebooks use them on Databricks. The seed supplies
every id, so the data and the results are the same either way.

If a cell fails on Databricks, a screenshot of the error is enough to fix it.

## Rebuilding
`python build_notebooks.py` regenerates `notebooks/` and the zip from `src/` templates and the
project's own files:
- Exercise 1: the two CSVs;
- Exercise 2: `mock_api.py` and the retry and validation code from `ingest.py`;
- Exercise 3: `ddl.sql` translated to Delta, and `seed.sql`.

So the Databricks version can't drift from the MySQL one.
