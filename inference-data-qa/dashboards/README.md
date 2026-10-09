# Employee 360 Data Quality dashboard (Databricks AI/BI)

`employee360_dq.lvdash.json` is the serialized AI/BI (Lakeview) dashboard **"Employee 360 Data Quality"**. It
reads the result tables written by `notebooks/employee360_medallion.py` in `workspace.employee360_medallion`.
The catalog and schema are written into each dataset query. To point it at another schema, replace
`workspace.employee360_medallion` in the file. Run evidence: [`../evidence/databricks_dashboard.md`](../evidence/databricks_dashboard.md).

## Which run each page shows
The pipeline ran three times into the schema:
- run 1: the supplied extracts;
- run 2: the same files, skipped;
- run 3: `data/simulated_run3`, a **simulated** delivery with fixes.

The headline numbers come from the supplied data (run 1). Anything from run 3 is labelled
"Run 3 (simulated delivery)".

`gold_employee_360` and `silver_e360_delivered` are rebuilt on every run, so after run 3 they hold the simulated
delivery. Two snapshot tables keep the run 1 state, taken with Delta time travel at the version run 1 wrote:
- `gold_employee_360_supplied`
- `silver_e360_delivered_supplied`

To recreate them, find run 1's version with `DESCRIBE HISTORY`, then run:
```sql
CREATE OR REPLACE TABLE workspace.employee360_medallion.gold_employee_360_supplied AS
SELECT * FROM workspace.employee360_medallion.gold_employee_360 VERSION AS OF <run 1 version>;
CREATE OR REPLACE TABLE workspace.employee360_medallion.silver_e360_delivered_supplied AS
SELECT * FROM workspace.employee360_medallion.silver_e360_delivered VERSION AS OF <run 1 version>;
```

## Pages
### 1. Release gate (supplied data)
- **Text box:** what BLOCK means and where the data comes from.
- **Counters:**
  - release decision (BLOCK);
  - rules failing (10 of 10);
  - blocking rules failing (5);
  - employees with at least one failure (13);
  - Gold trusted records (40 of 48).
- **Bar chart:** affected employees per rule, coloured by severity (Critical red, High orange, Medium amber).
- **Monitoring table:** rule, description, dimension, status, severity, action, alert threshold, owner and affected IDs.

### 2. Reconciliation and Gold
- **Gold vs delivered Employee 360:**
  - employees: 48 vs 48;
  - active employees: 45 vs 46;
  - verified ZAR salaries: 45 vs 48;
  - trusted records: 40 in Gold.
- **Untrusted Gold employees (8):** status, payroll status, salary and `dq_rules_failed`.
- **Failure detail for run 1:** 20 rows of rule, employee, source and detail, with a filter on rule.

### 3. Pipeline runs and issue lifecycle
- **Grouped bar chart:** new, resolved and open issues per run from `dq_runs`. Run 3 is labelled as simulated.
- **`dq_issues` table:** its state after Run 3 (simulated delivery), with a status filter (Open or Resolved).
- **`ingest_batches`:** for each source and batch, the rows in the file, rows inserted, rows already loaded
  (skipped), rows no longer delivered, and whether the whole file was skipped.

## Datasets
`M` = `workspace.employee360_medallion`.

| Dataset | SQL in brief |
|---|---|
| `gate_kpis` | From `M.gold_dq_monitoring WHERE run_id = 1`:<br>• BLOCK if any `blocks_release`<br>• count of FAIL rules<br>• count of blocking rules<br>From run 1 of `dq_failure_detail` (earliest `run_ts`): distinct employees<br>From `gold_employee_360_supplied`: trusted records of all records |
| `rules` | `M.gold_dq_monitoring WHERE run_id = 1`, ordered by severity |
| `gold_vs_delivered` | Counts from `gold_employee_360_supplied` and `silver_e360_delivered_supplied` (the same measures as `sql/10_silver_gold.sql`) |
| `gold_untrusted` | `gold_employee_360_supplied WHERE NOT is_trusted` |
| `failure_detail` | `M.dq_failure_detail WHERE run_ts = (SELECT min(run_ts) ...)` (run 1) |
| `runs` | `M.dq_runs` unpivoted with `stack(3, 'New', ..., 'Resolved', ..., 'Open', ...)`, with run labels |
| `issues` | `M.dq_issues` |
| `batches` | `M.ingest_batches`:<br>• `rows_unchanged = rows_in_file - rows_inserted`<br>• the run that loaded each batch (the first `dq_runs.run_at` at or after `loaded_at`) |

## Redeploy
**Asset Bundle:** add a `dashboards` resource to `databricks.yml` and run `databricks bundle deploy`:
```yaml
resources:
  dashboards:
    employee360_dq:
      display_name: Employee 360 Data Quality
      file_path: ./dashboards/employee360_dq.lvdash.json
      warehouse_id: <serverless SQL warehouse id>
      embed_credentials: true
```

**REST API:**
```bash
# create a draft
curl -X POST "$HOST/api/2.0/lakeview/dashboards" -d @- <<JSON
{"display_name": "Employee 360 Data Quality", "warehouse_id": "<id>",
 "parent_path": "/Workspace/Users/<user>/inference-data-qa",
 "serialized_dashboard": <contents of employee360_dq.lvdash.json as a JSON string>}
JSON

# publish it
curl -X POST "$HOST/api/2.0/lakeview/dashboards/<dashboard_id>/published" \
     -d '{"embed_credentials": true, "warehouse_id": "<id>"}'
```
To update an existing dashboard, `PATCH /api/2.0/lakeview/dashboards/<dashboard_id>` with a new
`serialized_dashboard`, then publish again.
