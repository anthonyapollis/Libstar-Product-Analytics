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
