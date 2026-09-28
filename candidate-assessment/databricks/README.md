# Databricks version (WORK IN PROGRESS)

**Status: in progress. Not yet passing its local test. Please don't review it yet.**

The same three exercises, on the same data, as Databricks notebooks (Delta Lake, Unity Catalog):
- `src/`: notebook templates.
- `build_notebooks.py`: fills the templates from the project's own files (the Exercise 1 CSVs, the
  Exercise 2 mock API and ingest code, the Exercise 3 DDL and seed) and writes `notebooks/`.
- `run_local.py`: runs the notebooks with open-source Spark 4 and Delta 4, as a test before they're
  handed over for Databricks Free Edition.

Import and run instructions will follow here once the local test passes.
