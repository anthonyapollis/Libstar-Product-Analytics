# Databricks execution

Upload `src/employee360_pipeline.py` and the three CSVs to a workspace folder or repository. Run the module with the corresponding workspace paths. The local executable test is the source-controlled regression gate; the SQL files are intended for Databricks SQL validation against managed source tables.

Do not use `first()` to choose a payroll record after aggregation. Preserve a conflicting employee/pay-period as `Cannot verify` until the payroll owner corrects it.
