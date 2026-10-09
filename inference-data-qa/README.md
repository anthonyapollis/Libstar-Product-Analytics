# Employee 360 data-quality checks (Inference Group QA challenge)

Spark SQL and PySpark checks that find what is wrong in the consolidated Employee 360 view, reconcile it
to HR and payroll, and produce one monitoring table with a release decision. The same code runs on
Databricks and on local PySpark.

**Result for this delivery: BLOCK.** Every one of the 10 rules fails.
- Employee 360 is missing a real employee (E1027) and includes an invented one (E1099, a copy of E1028).
- It shows a terminated employee as active (E1012).
- It carries salaries that cannot be traced or verified.

Row counts (48 in each file) and salary totals hide all of this. Payroll also still has a leaver as payable
(E1029). See [docs/findings.md](docs/findings.md).

**Read first: [`Employee360_DQ_eBook.pdf`](Employee360_DQ_eBook.pdf)** (22 pages). It has an executive summary, a requirements index
that maps every task in the brief to a page, charts drawn from the outputs, run evidence, and an evidence index.

## What is where
| Brief task | Where |
|---|---|
| 1. Profile and prioritise | `sql/01_profile.sql` → `outputs/profile_*.csv`; top three findings in `docs/findings.md` §2 |
| 2. Executable checks (6, across 6 dimensions) | `sql/02_checks.sql` (CTEs, window functions, anti-joins) → `outputs/check_failures.csv` |
| 3. Reconciliation | `sql/03_reconciliation.sql` (keys, counts, net against gross salary) and PySpark `reconcile_fields` in `notebooks/employee360_dq.py` → `outputs/recon_*.csv`; summary in `docs/findings.md` §3 |
| 4. Root cause | `docs/findings.md` §4, evidence `outputs/recon_lookalike.csv` |
| 5. Monitoring output | `outputs/monitoring.csv` (rule, pass/fail, affected count, severity, action, alert threshold, release gate, IDs) |
| 6. Azure Databricks and DevOps, cost | `docs/operations.md`, `databricks.yml`, `azure-pipelines.yml`, `notebooks/employee360_incremental.py` |
| Medallion layers (Bronze → Silver → Gold) | `notebooks/employee360_medallion.py`, `sql/10_silver_gold.sql` → `outputs/medallion_*.csv` (see below) |
| Dashboard (Databricks AI/BI) | `dashboards/employee360_dq.lvdash.json`, `dashboards/README.md`, evidence `evidence/databricks_dashboard.md` (private, owner-only) |
| AI use | `docs/ai_use.md` |
| Video | `docs/walkthrough_script.md` |

## Medallion layers
| Layer | Tables | Holds |
|---|---|---|
| Bronze | `bronze_hr`, `bronze_payroll`, `bronze_e360`, `ingest_batches` | Every delivered row as a string, with its batch. Loaded incrementally: an unchanged file is skipped and changed rows are `MERGE`d on a row hash. |
| Silver | `silver_hr`, `silver_payroll`, `silver_e360_delivered` | The current delivery, typed and standardised. The checks run on these definitions. |
| Gold | `gold_employee_360`, `gold_dq_monitoring`, `dq_issues` | A trusted Employee 360 rebuilt from Silver by the ownership rules, the monitoring history and the open/resolved issues. |

**Gold rules:**
- HR decides who exists and their status, department, location and manager.
- Payroll supplies salary only when it holds exactly one valid ZAR value. Otherwise the salary is left empty
  and flagged, never guessed.
- Each employee's failing source rules are listed in `dq_rules_failed`.

**Gold against the delivered Employee 360 (supplied data, `outputs/medallion_gold_vs_delivered.csv`):**

| | Gold | Delivered |
|---|---:|---:|
| Active employees | 45 | 46 |
| Verified ZAR salaries | 45 | 48 |
| Trusted records | 40 of 48 | n/a |

Gold has E1027 and not E1099, shows E1012 as Terminated, and gives E1018's salary as R62,900.

## Run it
**Locally** (Python 3.10+ and Java 17):
```bash
pip install "pyspark==4.0.*" "delta-spark==4.0.*"
python run_local.py                 # profile, checks, reconciliation, monitoring -> outputs/*.csv
python tests/check_expected.py      # independent plain-Python recomputation: expects 10/10
python run_incremental_local.py     # Bronze -> Silver -> Gold, 3 runs (load, unchanged rerun, fixes + new issue)
```

**On Databricks:** import the folder into the workspace, keeping the layout, with notebooks as notebooks and
`sql/` and `data/` as files. Then:
- run `notebooks/employee360_dq` with widgets `as_of_date=2026-10-08`, `snapshot_end=2026-10-31` and
  `target_schema`;
- or run `notebooks/employee360_medallion` (Bronze → Silver → Gold, incremental) with `batch_dir=data`.

Results are appended to Delta tables in `target_schema`. Run evidence is in `evidence/databricks_run.md`.

## Assumptions
- **Join key:** `employee_id` is the join key.
- **Ownership:** HR owns status, manager, department and location; payroll owns salary, currency and payroll status.
- **Dates:**
  - **reporting month:** October 2026;
  - **extract date:** 2026-10-08, the newest `last_updated` in any file;
  - **stale:** not updated in the 30 days before that date;
  - **future-dated:** an HR effective date after 31 October. Employee 360 should still show the October value, so
    this is a legitimate exception, not an error.
- **Values:**
  - **location:** "CPT" is Cape Town;
  - **managers:** a blank manager is allowed only for someone who manages others (E1001–E1005);
  - **payroll period:** 2026-09 is the latest payroll available for the October snapshot.
- **Leavers:** HR Terminated should mean payroll Stopped. Whether E1029's September pay is legitimately due is
  for payroll to confirm; the check flags the inconsistency.
- **Conflicting salaries:** where payroll holds two different salaries for one employee (E1015), Employee 360's
  value is reported as **Cannot verify**, not as correct.

## Limitations
- **Not executed:** `databricks.yml` and `azure-pipelines.yml`, because no Azure workspace or DevOps project was
  available. The notebooks themselves ran on Databricks Free Edition serverless and locally.
- **Simulated data:** `data/simulated_run3/` is a labelled, simulated delivery used only for the incremental
  demo; it is not supplied data.
- **Changed keys:** at this size the row-level checks re-run on the full current snapshot when anything changes.
  The changed-key list is computed and would be used to filter them at scale.
- **Root cause:** a hypothesis. Confirming it needs the identity crosswalk, the Delta history and the job logs
  (listed in findings §4).
