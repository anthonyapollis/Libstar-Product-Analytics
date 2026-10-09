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
