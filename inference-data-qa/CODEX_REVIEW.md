# Codex review: Employee 360 data-QA challenge

Branch `claude/inference-data-qa`, folder `inference-data-qa/`. Claude builds; Codex validates and proposes
improvements here. Please add findings as numbered sections (QA-01, QA-02, …) with a verdict
(APPROVED / REWORK REQUIRED) and, for rework, the exact change wanted. Claude replies under each one.

The brief is the client's "Data Quality Assurance Engineer – Technical Challenge" (not committed). It favours *a small,
working, explainable solution with strong judgement* over an elaborate framework, and has a 2.5-hour timebox.

## What to validate
1. **Correctness:** run `python run_local.py` then `python tests/check_expected.py`, which should report 10/10.
   Do the affected IDs in `outputs/monitoring.csv` match your own reading of the three CSVs?
2. **Judgement:** are the legitimate exceptions (CPT, E1042 future-dated, blank top-level managers) and the E1029
   leaver caveat right? Is anything an error that we call fine, or fine that we call an error?
3. **Brief coverage:** tasks 1–6 and the AI-use questions are mapped in `README.md`. Is anything missing or thin?
4. **Root cause** (`docs/findings.md` §4): are facts and hypotheses cleanly separated?
5. **Databricks:** `evidence/databricks_run.md`, being added by a separate session that runs the notebooks on the
   user's workspace. Do its results match the local outputs?
6. **Size:** anything that should be cut to stay within the spirit of the timebox?

## Status
- Local PySpark 4.0.4: `run_local.py` OK, `run_incremental_local.py` OK, `check_expected.py` 10/10.
- **Databricks serverless:** `employee360_dq` and three `employee360_incremental` runs succeeded. They match the local
  results on all 10 rules, all 3 runs and all 19 issue rows (`evidence/databricks_run.md`). The first run failed on a
  correlated scalar subquery that Databricks rejects and open-source Spark accepts; it is fixed, and both engines pass.
- **Medallion on Databricks:** three named runs, all successful on the first attempt. Gold after run 1 matches the local
  output in all 576 cells; the run log, all 19 issue rows and all 10 monitoring rules match too
  (`evidence/databricks_run.md`, with images of the run exports).
- **Dashboard "Employee 360 Data Quality"** (`dashboards/employee360_dq.lvdash.json`): three pages. The reconciliation
  categories show E1042 as a legitimate exception that is not counted as a failure. Every dataset was checked against
  the local outputs. Access is private: owner and admins only, embedded credentials off, no shares or schedules
  (`evidence/databricks_dashboard.md`).
- **eBook:** `Employee360_DQ_eBook.pdf`, 20 pages. Every table is read from `outputs/` or `evidence/`, and every image is
  listed in Appendix B with its kind and SHA-256. Screenshots of the dashboard, taken by the candidate, are still to
  come; they will go in as genuine captures (`ebook/img/genuine_*.png`).
- **Please verify:** the eBook's claims against the outputs, and the dashboard evidence.
