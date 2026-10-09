# Employee 360 Data Quality: Databricks AI/BI dashboard evidence

- **Date:** 2026-10-09 (all times UTC)
- **Workspace:** `dbc-ea48b979-9753.cloud.databricks.com` (Free Edition, serverless)
- **Dashboard:** "Employee 360 Data Quality", id `01f1c4297bf619938e952fea8dfa289b`
  - Published: https://dbc-ea48b979-9753.cloud.databricks.com/dashboardsv3/01f1c4297bf619938e952fea8dfa289b/published
  - Draft: https://dbc-ea48b979-9753.cloud.databricks.com/dashboardsv3/01f1c4297bf619938e952fea8dfa289b
  - Workspace path: `/Users/<user>/inference-data-qa/Employee 360 Data Quality.lvdash.json`
- **Warehouse:** Serverless Starter Warehouse (`bc1f90f992e51d23`, serverless)
- **Publication:**
  - created with `POST /api/2.0/lakeview/dashboards` at 21:36:27;
  - first published with `embed_credentials: true` at 21:36:35, as the build brief asked;
  - republished with `embed_credentials: false` at 21:37:42 (current), to match the access decision recorded in
    `docs/operations.md` and the bundle in `databricks.yml` (private, owner-only, embedded credentials off).
- **Access:** `GET /api/2.0/permissions/dashboards/<id>` lists only the owner (CAN_MANAGE) and the workspace
  `admins` group (CAN_MANAGE). There are no other users, groups, shares or embed links.
- **Definition:** [`../dashboards/employee360_dq.lvdash.json`](../dashboards/employee360_dq.lvdash.json). This is
  the `serialized_dashboard` the server returned from `GET`. It has 8 datasets and 3 pages with 16 widgets.
- **Description of the pages:** [`../dashboards/README.md`](../dashboards/README.md).

## Source data: `workspace.employee360_medallion`
These tables were written by another session's three runs of `notebooks/employee360_medallion.py`. All three
runs succeeded.

| run_id | Job run name | batch_dir | `dq_runs.run_at` |
|---|---|---|---|
| 1 | Medallion run 1 of 3, supplied data, full load | `data` | 21:16:29 |
| 2 | Medallion run 2 of 3, same files again, should skip | `data` | 21:18:10 |
| 3 | Medallion run 3 of 3, simulated fixes and 1 new issue | `data/simulated_run3` | 21:34:25 |

These are not the runs in `databricks_run.md`; those wrote to `workspace.employee360_dq`.

I polled for this schema every 2 minutes from 20:26. At 60 minutes, runs 1 and 2 had finished and run 3 had
not. A first job run (`employee360_medallion_run1`) had been cancelled by the user after about an hour without
writing anything. The headline numbers need only run 1, so I took the run 1 snapshots then. I waited about 8 more
minutes for run 3 instead of falling back to `workspace.employee360_dq`. Run 3 landed at 21:34, so the
dashboard uses the medallion schema throughout.

### Run 1 snapshots (Delta time travel)
`gold_employee_360` and `silver_e360_delivered` are rebuilt on every run that executes the checks, so after run 3
they hold the simulated delivery. In `DESCRIBE HISTORY`, version 0 of each table was the run 1 write: the
`CREATE OR REPLACE TABLE AS SELECT` at 21:16:56 and 21:16:47, before run 2 (which skipped) and before run 3.
I snapshotted version 0 of each:

```sql
CREATE OR REPLACE TABLE workspace.employee360_medallion.gold_employee_360_supplied AS
SELECT * FROM workspace.employee360_medallion.gold_employee_360 VERSION AS OF 0;
CREATE OR REPLACE TABLE workspace.employee360_medallion.silver_e360_delivered_supplied AS
SELECT * FROM workspace.employee360_medallion.silver_e360_delivered VERSION AS OF 0;
```

The second snapshot is needed for the "delivered" column of Gold vs delivered. Without it, that column would show
run 3's simulated Employee 360.

I compared `gold_employee_360_supplied` with `outputs/medallion_gold_employee_360.csv` cell by cell, across all
12 columns, ordered by `employee_id` (case-insensitive booleans, arrays joined with ", "). Results:
- 48 rows on each side;
- 0 differing rows;
- 45 Active;
- 40 trusted.

### Which rows are "run 1"
- **`gold_dq_monitoring`:** filtered `run_id = 1`. It has 10 rows for run 1 and 10 rows for run 3; run 2 skipped
  the checks.
- **`dq_failure_detail`:** this table has no `run_id`, so run 1 is the earliest `run_ts`. That is 21:15:54, with
  20 rows. Run 3 is 21:33:52, with 14 rows.

## Dataset queries checked before the dashboard was created
I ran every dataset's SQL through the SQL Statement API on the same warehouse, then compared the results with the
local outputs. All queries succeeded.

| Dataset | Rows | Checked against | Result |
|---|---:|---|---|
| `gate_kpis` | 1 | `outputs/monitoring.csv`, `outputs/failure_detail.csv`, Gold CSV | BLOCK; rules failing "10 of 10"; blocking rules 5; employees with ≥1 failure 13; Gold trusted "40 of 48". All as expected. |
| `rules` | 10 | `outputs/monitoring.csv` | 11 columns compared on all 10 rules, including the alert threshold, with 0 mismatches. Blocking rules: DQ01, DQ05, RC01, RC02, RC03. |
| `gold_vs_delivered` | 4 | `outputs/medallion_gold_vs_delivered.csv` | Employees 48/48; active 45/46; verified ZAR salaries 45/48; trusted 40 in Gold. All 4 rows match. |
| `gold_untrusted` | 8 | Gold CSV, `is_trusted = False` | Same 8 IDs and `dq_rules_failed`: E1015 DQ01, E1020 DQ02, E1024 DQ03, E1029 DQ04, E1030 DQ06, E1035 DQ02, E1037 DQ05, E1044 DQ04. |
| `failure_detail` | 20 | `outputs/failure_detail.csv` | Identical set of (rule, employee, source, detail). |
| `runs` | 9 | `outputs/incremental_runs.csv` | New/resolved/open: run 1 17/0/17; run 2 0/0/17; run 3 2/8/11. Matches. Run 3 is labelled "Run 3 (simulated delivery)". |
| `issues` | 19 | `outputs/incremental_issues.csv` | Identical on rule, employee, status, first/last/resolved run and detail. 11 Open, 8 Resolved. |
| `batches` | 6 | `outputs/incremental_batches.csv` | Rows in file, inserted, dropped and skipped all match. Batch 1 rows are labelled "Run 1 (supplied data)"; batch 2 rows are labelled "Run 3 (simulated delivery)". |

The `batches` dataset adds `rows_unchanged = rows_in_file - rows_inserted` and labels it "Skipped (already
loaded)". The table's own `rows_dropped` counts rows from the previous batch that are no longer delivered, not
skipped rows, so the dashboard labels it "No longer delivered".

## Checks after the dashboard was created
- `GET /api/2.0/lakeview/dashboards/<id>` returned all 8 datasets with their query text unchanged.
- It returned all 3 pages with every widget unchanged:
  - page 1: text box, 5 counters, bar chart, table;
  - page 2: 2 tables, rule filter, failure detail table;
  - page 3: grouped bar chart, status filter, issues table, batches table.
- `GET .../published` shows the dashboard published on warehouse `bc1f90f992e51d23` with `embed_credentials: false`.
- The API accepted every widget spec: counter v2, bar v3, table v2, filter-multi-select v2 and a text box.
  Nothing had to be simplified.

## Limitations
- **No screenshots.** The logged-in dashboard UI could not be rendered from this session, so I have not seen the
  widgets drawn. The API accepting a widget spec does not prove it renders as intended. Things to check visually:
  - the severity colours on the rule bar chart;
  - text counters such as "BLOCK" and "10 of 10".

  Open the published URL, check each page and take screenshots for the evidence pack.
- **Snapshot tables are point-in-time.** `gold_employee_360_supplied` and `silver_e360_delivered_supplied` do not
  refresh. If the pipeline is rerun from scratch into a new schema, recreate them from the version that run 1
  wrote.
- **`dq_issues` and the "Open" bar show the state after run 3, the simulated delivery.** Page 3 says so. An issue
  marked Resolved there was fixed by the simulated files, not by the supplied data.
- **Another job wrote to the schema around publication.** While the dashboard was being published, another
  session's job ("Reconciliation detail for dashboard") was running against the supplied data. It does not change
  what run 1 means here:
  - later appends to `dq_failure_detail` have a later `run_ts`;
  - later appends to `gold_dq_monitoring` have a different `run_id`.

  If it replaces `gold_employee_360` again, the `_supplied` snapshots are unaffected.

## Reconciliation categories
Added to page 2 ("Reconciliation and Gold"): a `reconciliation_categories` dataset, a text box, a bar chart and a
table. Legitimate exceptions are shown, but they are not presented as failures.

### The run that wrote the reconciliation detail
`notebooks/employee360_dq.py` (commit 18aaf41) also saves `dq_recon_keys` and `dq_recon_fields`, including
legitimate exceptions. The notebook was re-imported to `/Workspace/Users/<user>/inference-data-qa/notebooks/employee360_dq`
(overwrite, PYTHON, SOURCE). It then ran once on the supplied CSVs in `data/`, after all three medallion runs had
finished, so the latest `run_ts` is the supplied data and not the simulated run 3.

| Run name | Task key | Parameters | Run ID | Result | Start → end |
|---|---|---|---|---|---|
| Employee360 DQ \| Reconciliation detail for dashboard \| supplied data | `reconciliation_detail_supplied_data` | as_of_date=2026-10-08, snapshot_end=2026-10-31, target_schema=workspace.employee360_medallion, fail_on_block=false | [886182844809097](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/825279651182009/run/886182844809097) | SUCCESS, first attempt, no code change | 21:36:13 → 21:38:09 (115 s) |

It appended:
- `dq_recon_keys`: all 49 keys, 47 of them Matched (run_ts 2026-10-09T21:37:54.368Z);
- `dq_recon_fields`: 9 rows (run_ts 2026-10-09T21:37:58.026Z).

Before this run, neither table existed in the schema. The same run also appended to `dq_monitoring` and
`dq_failure_detail` with a later `run_ts`. The page 1 datasets read `gold_dq_monitoring WHERE run_id = 1` and the
earliest `dq_failure_detail` run, so they are unchanged. After the update `gate_kpis` still returns BLOCK,
"10 of 10", 5, 13 and "40 of 48".

### Latest run vs local outputs (SQL Statement API)
- **`dq_recon_keys` vs `outputs/recon_keys.csv`:** the rows other than Matched are identical, compared on all six
  columns by name:
  - E1027 Tumi Mbatha, Missing downstream (in HR and payroll, not in Employee 360);
  - E1099 Unknown Legacy Employee, Unexpected downstream (only in Employee 360).
- **`dq_recon_fields` vs `outputs/recon_fields.csv`:** the 9 rows are identical on all 8 columns:
  - Error: E1012, E1018, E1037, E1044 (×2), E1020, E1033;
  - Cannot verify: E1015;
  - Legitimate exception: E1042.

### Dataset query result vs local outputs
The `reconciliation_categories` query was taken from the definition returned by `GET` and run on warehouse
`bc1f90f992e51d23`. Raw result: [`databricks_recon_categories.csv`](databricks_recon_categories.csv).

| Category | Employees | Employee IDs | counts_as_failure | Local outputs | Match |
|---|---:|---|---|---|---|
| Missing downstream | 1 | E1027 | true | `recon_keys.csv`: E1027 | yes |
| Unexpected downstream | 1 | E1099 | true | `recon_keys.csv`: E1099 | yes |
| Field error | 6 | E1012, E1018, E1020, E1033, E1037, E1044 | true | `recon_fields.csv` Error: the same 6 (E1044 on 2 fields) | yes |
| Cannot verify | 1 | E1015 | true | `recon_fields.csv`: E1015 | yes |
| Legitimate exception | 1 | E1042 | **false** | `recon_fields.csv`: E1042 (future-dated HR change) | yes |

E1042 does not appear in any failure dataset: `gate_kpis`, `rules`, `failure_detail` and `gold_untrusted` were
re-run, and none of them contains E1042.

### Dashboard update
- **Update:** `PATCH /api/2.0/lakeview/dashboards/01f1c4297bf619938e952fea8dfa289b` with the new
  `serialized_dashboard` and the current etag (`9148288357` → `389406813`).
- **New items on page 2, inserted at y = 5** (the rule filter and the failure detail moved down 12 rows):
  - `recon_categories_note`: a text box with the legitimate-exception statement;
  - `bar_recon_categories`: a bar chart of employees per category. Colour comes from `failure_label`:
    "Counts as failure" is red `#D32F2F` and "Not a failure" is grey `#9E9E9E`;
  - `t_recon_categories`: a table of category, employees, employee IDs, counts as failure, severity and meaning.
- **Republished** with `POST .../published` at 21:39:43, keeping `embed_credentials: false` and warehouse
  `bc1f90f992e51d23`. The build brief for this change asked for `embed_credentials: true`. The user's recorded
  decision is private, owner-only, with embedded credentials off (`docs/operations.md`, `databricks.yml`), so
  that setting was kept. Permissions are unchanged: only the owner and `admins` have CAN_MANAGE.
- **Check:** `GET` returned 9 datasets and 19 widgets, with `reconciliation_categories` and its query text
  unchanged and all 3 new widgets at their positions.
  - The only normalisation: the server joined the text box's lines that had no newline into one line. The text
    is the same.
  - `dashboards/employee360_dq.lvdash.json` is the `serialized_dashboard` from that `GET`.
- **Not seen rendered:** as above, the bar colours and the text box have not been checked visually.
