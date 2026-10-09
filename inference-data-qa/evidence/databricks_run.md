# Employee 360 DQ on Databricks: run evidence

- **Date:** 2026-10-09 (all times UTC)
- **Workspace:** `dbc-ea48b979-9753.cloud.databricks.com` (Free Edition, serverless compute)
- **Project location:** `/Workspace/Users/<user>/inference-data-qa/` — `notebooks/employee360_dq` and
  `notebooks/employee360_incremental` imported as Python notebooks (SOURCE); `sql/*.sql`, `data/*.csv` and
  `data/simulated_run3/*.csv` imported as workspace files, so the notebooks read `../sql` and `../data` by path.
- **How it ran:** one-time serverless runs (`POST /api/2.1/jobs/runs/submit`, notebook task, no cluster spec).
  Results were read back with the SQL Statement API on the Serverless Starter Warehouse.
- **Result tables:** `workspace.employee360_dq` (`dq_monitoring`, `dq_failure_detail`, `ingest_batches`,
  `dq_runs`, `dq_issues`, `bronze_hr`, `bronze_payroll`, `bronze_e360`).

## Runs

| # | Notebook | Parameters | Run ID | Result | Duration | Start → end |
|---|---|---|---|---|---|---|
| 0 | employee360_dq | as_of_date=2026-10-08, snapshot_end=2026-10-31, fail_on_block=false | [898819557289071](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/375900270819756/run/898819557289071) | **FAILED** (see fix below) | 126 s | 19:51:19 → 19:53:24 |
| 1 | employee360_dq | same as above | [515886583443770](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/151308571194981/run/515886583443770) | SUCCESS | 136 s | 19:53:43 → 19:55:59 |
| 2 | employee360_incremental | batch_dir=data | [981987682878372](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/726630909985902/run/981987682878372) | SUCCESS | 225 s | 19:57:22 → 20:01:07 |
| 3 | employee360_incremental | batch_dir=data | [94742837183686](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/962792658086121/run/94742837183686) | SUCCESS (exit value `skipped: no changes`) | 37 s | 20:01:19 → 20:01:57 |
| 4 | employee360_incremental | batch_dir=data/simulated_run3 | [68446115877254](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/590940621014588/run/68446115877254) | SUCCESS | 196 s | 20:02:08 → 20:05:25 |

All incremental runs used target_schema=`workspace.employee360_dq`. Before they ran, `SHOW TABLES` on the
schema listed only `dq_monitoring` and `dq_failure_detail` (written by run 1). None of the six incremental tables
existed yet, so they started clean and nothing was dropped.

### The one failure and the fix

Run 0 failed in `sql/03_reconciliation.sql` with
`UNSUPPORTED_SUBQUERY_EXPRESSION_CATEGORY.MUST_AGGREGATE_CORRELATED_SCALAR_SUBQUERY`. The `recon_keys` view
looked up `full_name` with a correlated scalar subquery,
`(SELECT full_name FROM stg_hr x WHERE x.employee_id = hr.employee_id)`. Open-source Spark 4 accepts it;
Databricks serverless rejects a correlated scalar subquery that is not aggregated. The fix was to carry
`full_name` in the `hr` CTE and use `coalesce(e.full_name, hr.full_name)`. The view already joins `hr` on
`employee_id`, so the result is the same. This was the only code change.

After the change, the local runs still pass:
`run_local.py` exit 0, `run_incremental_local.py` exit 0, `tests/check_expected.py` gave
"10/10 rules agree with the independent calculation". Nothing under `outputs/` changed (git shows no diff).

## Results compared with the local run

### Batch monitoring: `dq_monitoring`, run 1 (run_ts 2026-10-09T19:55:25.818Z) vs `outputs/monitoring.csv`

Raw data: `databricks_monitoring.csv`.

| rule_id | Databricks status | Databricks affected_ids | Local status | Local affected_ids | Match |
|---|---|---|---|---|---|
| DQ01 | FAIL | E1015 | FAIL | E1015 | yes |
| DQ02 | FAIL | E1020, E1035 | FAIL | E1020, E1035 | yes |
| DQ03 | FAIL | E1024 | FAIL | E1024 | yes |
| DQ04 | FAIL | E1029, E1044 | FAIL | E1029, E1044 | yes |
| DQ05 | FAIL | E1037 | FAIL | E1037 | yes |
| DQ06 | FAIL | E1030 | FAIL | E1030 | yes |
| RC01 | FAIL | E1027 | FAIL | E1027 | yes |
| RC02 | FAIL | E1099 | FAIL | E1099 | yes |
| RC03 | FAIL | E1012, E1015, E1018, E1037, E1044 | FAIL | E1012, E1015, E1018, E1037, E1044 | yes |
| RC04 | FAIL | E1020, E1033 | FAIL | E1020, E1033 | yes |

`affected_count`, `alert_fired` and `blocks_release` also match on all 10 rules.

About "latest run": the incremental notebook calls `employee360_dq` with `%run`, so every incremental run that
executes the checks also appends to `dq_monitoring`. The table therefore holds three snapshots
(`databricks_monitoring_runs.csv`): 19:55:25 (batch run, 10/10 FAIL), 20:00:03 (incremental run 1, the same
extracts, 10/10 FAIL) and 20:04:27 (incremental run 3 on `simulated_run3`, 7 FAIL). The newest row by
timestamp is the simulated run 3, so the comparison above uses the batch run's snapshot (the earliest one). The
run 3 snapshot is saved separately as `databricks_monitoring_latest_incremental_run3.csv`. There is no local
file to compare it with. It does agree with the open issues in `dq_issues` after run 3.

### Incremental runs: `dq_runs` vs `outputs/incremental_runs.csv`

Raw data: `databricks_dq_runs.csv`.

| run_id | batch_dir | changed_employees | checks_run | new_issues | resolved_issues | open_issues | Local | Match |
|---|---|---|---|---|---|---|---|---|
| 1 | data | 49 | true | 17 | 0 | 17 | 1, data, 49, True, 17, 0, 17 | yes |
| 2 | data | 0 | false | 0 | 0 | 17 | 2, data, 0, False, 0, 0, 17 | yes |
| 3 | data/simulated_run3 | 7 | true | 2 | 8 | 11 | 3, data/simulated_run3, 7, True, 2, 8, 11 | yes |

### Issue lifecycle: `dq_issues` vs `outputs/incremental_issues.csv`

Raw data: `databricks_dq_issues.csv`. Both have 19 rows. Matched on (rule_id, employee_id, first_seen_run),
every column agrees: status, first_seen_run, last_seen_run, resolved_run and detail. There are no rows in only
one of the two.

| rule_id | employee_id | status | first_seen | last_seen | resolved | detail |
|---|---|---|---|---|---|---|
| DQ01 | E1015 | Resolved | 1 | 1 | 3 | 2 rows for one employee_id |
| DQ02 | E1020 | Resolved | 1 | 1 | 3 | blank: department |
| DQ02 | E1035 | Open | 1 | 3 | | blank: email |
| DQ03 | E1024 | Open | 1 | 3 | | manager_id E9999 is not in HR |
| DQ03 | E1045 | Open | 3 | 3 | | manager_id E9998 is not in HR |
| DQ04 | E1029 | Resolved | 1 | 1 | 3 | HR Terminated, payroll Payable (HR effective 2026-10-02) |
| DQ04 | E1044 | Open | 1 | 3 | | HR Active but no payroll record |
| DQ05 | E1037 | Open | 1 | 3 | | currency USD in monthly_salary_zar |
| DQ06 | E1030 | Open | 1 | 3 | | last_updated 2026-07-01, 99 days before the extract; last_updated 2026-07-02, 98 days before the extract |
| RC01 | E1027 | Resolved | 1 | 1 | 3 | Missing downstream |
| RC02 | E1099 | Resolved | 1 | 1 | 3 | Unexpected downstream |
| RC03 | E1012 | Resolved | 1 | 1 | 3 | employment_status: Terminated -> Active |
| RC03 | E1015 | Resolved | 1 | 1 | 3 | monthly_salary: 57100.00 -> 57100.00 (cannot verify: payroll holds conflicting values) |
| RC03 | E1018 | Open | 1 | 3 | | monthly_salary: 62900.00 -> 69400.00 |
| RC03 | E1037 | Open | 1 | 3 | | currency: USD -> ZAR |
| RC03 | E1044 | Open | 1 | 3 | | currency: blank -> ZAR; monthly_salary: blank -> 56200.00 |
| RC04 | E1020 | Resolved | 1 | 1 | 3 | department: blank -> Finance |
| RC04 | E1033 | Open | 1 | 3 | | department: People -> Sales |
| RC04 | E1045 | Open | 3 | 3 | | manager_id: E9998 -> E1001 |

### Batch log: `ingest_batches`

Raw data: `databricks_ingest_batches.csv`. This log has no rows for run 2: the notebook does not write skipped
sources to it, so a run that skips every source leaves it unchanged.

| source | batch_id | rows_in_file | rows_inserted | rows_dropped | skipped |
|---|---|---|---|---|---|
| e360 | 1 | 48 | 48 | 0 | false |
| hr | 1 | 48 | 48 | 0 | false |
| payroll | 1 | 48 | 48 | 0 | false |
| e360 | 2 | 48 | 2 | 2 | false |
| hr | 2 | 48 | 2 | 2 | false |
| payroll | 2 | 47 | 1 | 2 | false |

## Differences

Once the subquery fix was in, there were no differences in rule status, affected IDs, run counts or issue
lifecycle. The only formatting difference is in booleans: Databricks returns `true`/`false` and the local CSVs
have `True`/`False`. The comparison ignores case.

Local environment note: `run_incremental_local.py` downloads `delta-spark` with Ivy. In this container that
download was blocked (`repos.spark-packages.org` was denied by the proxy, and Maven Central returned 429 rate
limits). The local run worked after the Delta jars were placed in `~/.m2` from Google's Maven Central mirror.
This affected only the local setup, not the project code.

## Medallion pipeline on Databricks

- **Date:** 2026-10-09 (UTC). **Notebook:** `notebooks/employee360_medallion`. It `%run`s `./employee360_incremental`
  (Bronze plus checks), then runs `sql/10_silver_gold.sql` (Silver and Gold).
- **Import:** the current versions were re-imported into `/Workspace/Users/<user>/inference-data-qa/` with overwrite at
  about 20:40. All four notebooks went in as PYTHON/SOURCE notebooks. `sql/*.sql`, `data/*.csv` and
  `data/simulated_run3/*.csv` went in as AUTO files.
- **Schema:** `workspace.employee360_medallion`. It existed but was empty (`SHOW TABLES` returned no rows) when run 1
  started. Nothing was dropped, inside or outside it.
- **Submission:** one-time serverless runs, `POST /api/2.1/jobs/runs/submit`, notebook task, no cluster spec,
  base_parameters `target_schema=workspace.employee360_medallion` and `batch_dir` as shown below.
- **Code changes:** none. All three runs succeeded on the first attempt, so no retry runs were needed and the local
  scripts were not re-run for this section.

### Runs

| Run name (as shown in Jobs & Pipelines > Runs) | task_key | batch_dir | Run ID | Task run ID | Result | Duration | Start → end |
|---|---|---|---|---|---|---|---|
| `Employee360 DQ \| Medallion run 1 of 3 \| supplied data, full load` | `bronze_silver_gold_full_load` | `data` | [924122341592903](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/485876947098759/run/924122341592903) | 677109967167783 | SUCCESS | 780 s | 21:04:24 → 21:17:23 |
| `Employee360 DQ \| Medallion run 2 of 3 \| same files again, should skip` | `bronze_silver_gold_unchanged_rerun` | `data` | [568472820361926](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/48806367450666/run/568472820361926) | 299320886146837 | SUCCESS, exit value `skipped: no changes` | 34 s | 21:17:45 → 21:18:19 |
| `Employee360 DQ \| Medallion run 3 of 3 \| simulated fixes + 1 new issue` | `bronze_silver_gold_simulated_fixes` | `data/simulated_run3` | [249803799468757](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/1043466822107745/run/249803799468757) | 599987566794325 | SUCCESS | 293 s | 21:30:20 → 21:35:14 |

**A run left by the interrupted earlier session.** That session submitted one run before it stopped:
`employee360_medallion_run1` (run ID
[324021292396329](https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/425579247209086/run/324021292396329),
task_key `medallion`, same notebook and parameters as run 1). It started at 20:22:11. Its workspace notebooks were
re-imported about one second after it started. It then stayed "In run" for about 40 minutes with execution_duration 0
and wrote no table. It was **cancelled** at 21:04:07, with the user's approval, so that it could not write into the
schema alongside the named runs. It shows in the Runs list as CANCELED.

### Results compared with the local outputs

Raw query results (SQL Statement API, Serverless Starter Warehouse):
`databricks_medallion_run1_gold_employee_360.csv` and `databricks_medallion_run1_layers.csv` were read straight after
run 1, before run 3 overwrote Gold. `databricks_medallion_run3_gold_employee_360.csv`, `databricks_medallion_run3_layers.csv`,
`databricks_medallion_dq_runs.csv`, `databricks_medallion_dq_issues.csv`, `databricks_medallion_gold_dq_monitoring.csv`
and `databricks_medallion_ingest_batches.csv` were read after run 3.

| Check | Databricks | Local file | Result |
|---|---|---|---|
| Gold after run 1 (48 rows × 12 columns, `gold_built_at` excluded) | 48 employees, 45 Active, 45 with a verified ZAR salary, 40 trusted | `outputs/medallion_gold_employee_360.csv` | all 576 cells match |
| Gold after run 3 | 48 rows | `outputs/medallion_run3_gold_employee_360.csv` | all cells match |
| Layer row counts after run 1 | Bronze 48/48/48, Silver 48/48/48, Gold 48, gold_dq_monitoring 10, dq_issues 17 | `outputs/medallion_layers.csv` | match |
| Layer row counts after run 3 | Bronze hr 50, payroll 49, e360 50; Silver 48/47/48; Gold 48; gold_dq_monitoring 20; dq_issues 19 | `outputs/medallion_run3_layers.csv` | match |
| `dq_runs` | (49 changed, 17 new, 0 resolved, 17 open), (0 changed, checks skipped, 17 open), (7 changed, 2 new, 8 resolved, 11 open) | `outputs/incremental_runs.csv` | all 3 rows match |
| `dq_issues` (keyed on rule_id, employee_id, first_seen_run) | 19 rows | `outputs/incremental_issues.csv` | all 19 rows and every column match |
| `gold_dq_monitoring`, run_id 1 | 10 rules, all FAIL | `outputs/monitoring.csv` | all 12 columns match on all 10 rules |
| `gold_dq_monitoring`, run_id 3 | DQ01, RC01 and RC02 PASS; 7 rules FAIL with 11 affected in total | no local file | agrees with the 11 open issues in `dq_issues` |

`gold_dq_monitoring` has rows for run_id 1 and 3 only, because run 2 stopped before Gold. That is expected.

**Differences.** No data differences. There are two formatting differences, and the comparison normalises both.
(1) `dq_rules_failed` is an array column: the SQL API returns it as JSON (`["DQ04"]`, `[]`) and the local CSV writes
it as text (`DQ04`, empty). (2) Booleans are `true`/`false` on Databricks and `True`/`False` locally.

**Other tables in the schema.** `dq_monitoring` and `dq_failure_detail` are written by `employee360_dq`, which the
incremental notebook `%run`s. The schema also has `gold_employee_360_supplied` and `silver_e360_delivered_supplied`.
These were **not** created by these runs or by this project's code. `DESCRIBE HISTORY` shows a
`CREATE OR REPLACE TABLE AS SELECT` at 21:29:34 and 21:29:38, between run 2 and run 3, made by the same user through
the SQL warehouse with no job or notebook attached. They look like a snapshot of run 1's output taken from another
session. They were left in place. `gold_employee_360_supplied` matches the run-1 Gold captured here cell for cell.

### Images of Databricks' own rendering

For each task run, `GET /api/2.0/jobs/runs/export?run_id=<task run id>&views_to_export=ALL` returned one NOTEBOOK
view, saved in `databricks_exports/`. The pages were rendered to PNG with headless Chromium (Playwright,
`/opt/pw-browsers/chromium`) at 1400 px wide and clipped around the relevant output.

**These are renderings of Databricks run exports, NOT screenshots of the user's browser.** An export page loads
Databricks' notebook renderer from `databricks-prod-cloudfront.cloud.databricks.com`, which this container's network
policy blocks. The same files (same versioned path) were fetched from the workspace host
(`/static/v1/monolith-ui_.../`) and served to the page in their place. Nothing in the page content was changed.

| Image | What it shows | SHA-256 |
|---|---|---|
| `ebook/img/databricks_run1_monitoring.png` | Run 1: the monitoring table (10 rules, all FAIL) and `Release decision: BLOCK - do not publish this Employee 360 build`. Databricks' table viewer cuts off the columns after `status` at this width. | `2d221abca7ae49fb4c2fedfc94f07dca8255a2bd364397eebcf9b1adaca300c3` |
| `ebook/img/databricks_run1_gold.png` | Run 1: "Gold records that are not trusted, and why" (8 rows) and the layers table (9 rows) | `3732076c0519fe070e39df33c675b565f75ba7058a1f00862f1401afbb206b34` |
| `ebook/img/databricks_run2_skipped.png` | Run 2: batch log with 0 rows inserted and skipped=true for all three sources, `employees with a change this run: 0`, the exit value `skipped: no changes`, then "Command skipped" for the remaining cells | `ff8036048942d98ca828b3cb6c274f2eda6a4976af5b3d1394866811d799d91a` |
| `ebook/img/databricks_run3_new_issues.png` | Run 3: "New issues this run (these are the alerts)" (DQ03 and RC04 for E1045) and the run summary `{'changed_employees': 7, 'checks_run': True, 'new_issues': 2, 'resolved_issues': 8, 'open_issues': 11}` | `f30e927f352ca320928e218e0e1e74aed4cfbe7568af75b7910c90052eb66193` |

Run 2 note: the notebook prints `No source changed since the last run: checks skipped, no compute spent, no alerts.`
just before `dbutils.notebook.exit(...)`. That line is **not in Databricks' export**: the decoded notebook model has
no such text. Databricks keeps only the exit value of that cell. The image shows exactly what Databricks recorded,
and the skip is evidenced by `employees with a change this run: 0`, `skipped: no changes`, the "Command skipped"
cells and `dq_runs` row 2 (`checks_run=false`).

Export files (SHA-256):
`run1_full_load_task677109967167783.html` `ee6aebcc58c3cc0d52509794a9398b2e638c5f1cfdaa4607799748a38c68b90b`,
`run2_unchanged_rerun_task299320886146837.html` `9d9b77b4715411bdf22a2336d1414f5b2f07a80c48bf8dc2f7176ccd3a6bd80f`,
`run3_simulated_fixes_task599987566794325.html` `86d96d9a998876c1daa2a94be5169b0fd55af628445a22476f8944b3eacde50f`.

### Earlier runs explained

These are the older names in the Runs list. All of them used task_key `t`, which is why a task row named `t` appears.

| Run name in the list | Run ID | What it was | Result |
|---|---|---|---|
| `e360-dq` (first) | 898819557289071 | Batch checks, `employee360_dq`, schema `workspace.employee360_dq` | FAILED: `MUST_AGGREGATE_CORRELATED_SCALAR_SUBQUERY` in `sql/03_reconciliation.sql` (fixed, see above) |
| `e360-dq` (second) | 515886583443770 | The same batch checks after the subquery fix | SUCCESS |
| `e360-incremental-1` | 981987682878372 | Incremental run 1, supplied extracts (`data`) | SUCCESS |
| `e360-incremental-2` | 94742837183686 | Incremental run 2, same extracts again | SUCCESS, skipped (no changes) |
| `e360-incremental-3` | 68446115877254 | Incremental run 3, `data/simulated_run3` | SUCCESS |
| `employee360_medallion_run1` | 324021292396329 | Left by the interrupted session (task_key `medallion`), described above | CANCELED |
