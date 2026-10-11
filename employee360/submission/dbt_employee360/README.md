# dbt addition: Employee 360 SQL transformation layer

This small dbt project improves the assignment by making the SQL part of the solution reproducible, documented and testable.

## Role split

- **PySpark:** ingest CSVs, apply the 10 data-quality controls, use file hashes for incremental processing, and write Delta issue/monitoring tables.
- **dbt:** create documented staging and reconciliation models, expose model-level tests and lineage, and run a controlled SQL build in CI/CD.

## Run in a Databricks-connected environment

1. Install `dbt-databricks`.
2. Copy `profiles.yml.example` to your dbt profiles directory and set the workspace host, SQL warehouse HTTP path and `DATABRICKS_TOKEN`.
3. Ensure the PySpark ingestion job has created the three `raw` source tables.
4. Run:

```bash
dbt deps
dbt build --project-dir dbt_employee360 --profiles-dir <profiles-directory>
```

`int_payroll_conflicts` intentionally preserves payroll conflicts. The reconciliation mart treats them as `CANNOT_VERIFY`; it never uses an arbitrary grouped `first()` value.
