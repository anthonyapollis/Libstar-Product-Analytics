# Running it in Azure Databricks and Azure DevOps

## In Databricks
- **One job, two tasks** (`databricks.yml`):
  1. `dq_checks` runs `employee360_medallion`. That loads Bronze incrementally, runs the checks on the Silver
     definitions with `fail_on_block=true`, and rebuilds Silver and Gold.
  2. `publish_employee360` runs only if `dq_checks` succeeds.

  A blocking rule therefore stops publication. The results are saved first, so the evidence is never lost.
- **Results are Delta tables:**
  - `dq_monitoring`: one row per rule per run (the dashboard / trend source);
  - `dq_failure_detail`: affected IDs per run;
  - `dq_issues`: the open/resolved lifecycle;
  - `dq_runs` and `ingest_batches`: the run log.
- **Compute:** serverless jobs compute, so nothing is billed between runs. A classic job cluster would also
  work: single node, the smallest size, auto-terminate. The data is tiny; compute should start, run for
  minutes and stop.

## In Azure DevOps (`azure-pipelines.yml`)
| When | What runs | Databricks cost |
|---|---|---|
| Every pull request | **On the build agent with local PySpark, not Databricks:** `run_local.py` on the fixture CSVs and `tests/check_expected.py`, which must report 10/10. Any change to a rule must also change the expected results. | none |
| Merge to main | `databricks bundle validate`, then `databricks bundle deploy -t test` and one smoke run of the job on the fixture data in the test workspace | one short run |
| Release | `databricks bundle deploy -t prod` (approval gate on the prod environment) | none |
| On schedule (prod) | The job, daily at 06:00 after the HR and payroll extracts land, or on file arrival | a few minutes |

The workspace credential is a service principal stored in an Azure DevOps variable group linked to Key Vault.
Never use a personal token.

## Who gets alerted
- **Critical, consistency (DQ04, e.g. a leaver still payable):** payroll operations and HR operations, the same
  day, by email or Teams from a Databricks SQL alert on new `dq_issues` rows. Before the pay-run cut-off, it is
  re-checked 3 working days ahead.
- **Blocking failure (job fails):** the Employee 360 data engineering on-call, through the job's failure
  notification.
- **High / Alert now (DQ03, RC04):** the HR data steward, through a ticket or email for new issues only.
- **Medium / Monitor (DQ02, DQ06):** a weekly digest to data stewards, alerting only above the threshold.

## Keeping cost and noise down
- **No repeated full scans:**
  - an extract whose SHA-256 matches the last loaded one is not read at all (run 2 of the demo: 0 rows read,
    0 checks run);
  - changed extracts are `MERGE`d on a row hash, so only new or changed rows are written;
  - at scale, the row-level checks would be filtered to the changed keys the notebook already lists.
- **No noisy alerts:** `dq_issues` keeps one row per (rule, employee).
  - A failure alerts once, when it first appears.
  - It is not repeated while it stays open.
  - It is closed when it stops failing.
  - Run 3 of the demo raised 2 alerts, not one for each of the 11 failures still open.
- **No paid tools:** the checks are plain SQL and PySpark in the same job, and their history is Delta tables.
  There is no separate data-quality or observability licence. Delta Live Tables expectations would be an
  option, but they add a pipeline product and its cost for something a SQL view already does.
- **One SQL dialect:** the same `sql/*.sql` files run on the build agent's open-source Spark and on Databricks.
  CI therefore needs no workspace, and a Databricks-only feature (e.g. `QUALIFY`) would fail in CI.

## A check I would not run on every pipeline execution
**The full profile (`01_profile.sql`) and the look-alike search (R4 in `03_reconciliation.sql`).**
- The profile scans every column of every table.
- The look-alike search compares each unexpected record with every other record (a self-join that grows with
  the square of the table size).
- Both produce diagnostic insight, not a pass/fail gate, and the answers change slowly.

So I would run them weekly and on demand during an investigation, not after each load.
