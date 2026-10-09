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
- **Medallion (Bronze → Silver → Gold):** built and run locally; the Databricks run (named runs, plus images of the run
  exports) is in progress.
- **eBook:** `Employee360_DQ_eBook.pdf`, 18 pages. Every table is read from `outputs/`, and every image is listed in
  Appendix B with its kind and SHA-256. Please also check that the eBook's claims match the outputs.
