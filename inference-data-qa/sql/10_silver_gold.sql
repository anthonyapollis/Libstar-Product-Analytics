-- Silver and Gold layers (Spark SQL, Delta). Bronze is built by notebooks/employee360_incremental.py.
--   Bronze: the extracts exactly as delivered, every batch, as strings (bronze_hr, bronze_payroll, bronze_e360).
--   Silver: the current delivery, typed and standardised (dates parsed, CPT -> Cape Town); one table per source.
--   Gold:   what reporting should use: a trusted Employee 360 rebuilt from Silver by the ownership rules,
--           with each employee's open data-quality rules, plus the monitoring history.
-- Parameters: ${schema}, ${snapshot_end}. The view dq_failure_detail_v is this run's failures.

CREATE OR REPLACE TABLE ${schema}.silver_hr USING DELTA AS
SELECT * EXCEPT (effective_date_raw), current_timestamp() AS silver_loaded_at FROM stg_hr;

CREATE OR REPLACE TABLE ${schema}.silver_payroll USING DELTA AS
SELECT * EXCEPT (key_count), current_timestamp() AS silver_loaded_at FROM stg_payroll;

-- The delivered Employee 360 is itself a source under test, so it is kept in Silver for comparison.
CREATE OR REPLACE TABLE ${schema}.silver_e360_delivered USING DELTA AS
SELECT *, current_timestamp() AS silver_loaded_at FROM stg_e360;

-- Gold: one row per employee in HR (the system of record for who exists).
--   HR supplies identity, status, department, location and manager.
--   Payroll supplies salary and payroll status, but only when payroll holds exactly one valid ZAR value.
--   A conflicting or invalid salary is left empty and flagged, never guessed.
CREATE OR REPLACE TABLE ${schema}.gold_employee_360 USING DELTA AS
WITH pay AS (
  SELECT employee_id,
         count(*) AS payroll_rows,
         CASE WHEN count(DISTINCT monthly_salary) = 1 AND count(DISTINCT currency) = 1 AND max(currency) = 'ZAR'
                   AND max(monthly_salary) > 0 THEN max(monthly_salary) END AS monthly_salary_zar,
         CASE WHEN count(DISTINCT payroll_status) = 1 THEN max(payroll_status) END AS payroll_status
  FROM ${schema}.silver_payroll GROUP BY employee_id
),
flags AS (  -- source-quality rules only; RC rules describe the delivered Employee 360, not this rebuild
  SELECT employee_id, array_sort(collect_set(rule_id)) AS dq_rules_failed
  FROM dq_failure_detail_v WHERE rule_id LIKE 'DQ%' GROUP BY employee_id
)
SELECT h.employee_id, h.full_name, h.department, h.location, h.manager_id, h.employment_status,
       h.effective_date,
       h.effective_date > DATE'${snapshot_end}'                          AS future_dated_change,
       p.payroll_status, p.monthly_salary_zar,
       coalesce(f.dq_rules_failed, CAST(array() AS ARRAY<STRING>))      AS dq_rules_failed,
       f.employee_id IS NULL AND p.monthly_salary_zar IS NOT NULL        AS is_trusted,
       current_timestamp()                                               AS gold_built_at
FROM ${schema}.silver_hr h
LEFT JOIN pay p   ON p.employee_id = h.employee_id
LEFT JOIN flags f ON f.employee_id = h.employee_id;

-- Gold vs the delivered Employee 360: what reporting would show from each.
SELECT 'Employees' AS measure,
       (SELECT count(*) FROM ${schema}.gold_employee_360) AS gold,
       (SELECT count(*) FROM ${schema}.silver_e360_delivered) AS delivered_e360
UNION ALL
SELECT 'Active employees',
       (SELECT count_if(employment_status = 'Active') FROM ${schema}.gold_employee_360),
       (SELECT count_if(employment_status = 'Active') FROM ${schema}.silver_e360_delivered)
UNION ALL
SELECT 'Employees with a verified ZAR salary',
       (SELECT count(monthly_salary_zar) FROM ${schema}.gold_employee_360),
       (SELECT count(monthly_salary) FROM ${schema}.silver_e360_delivered)
UNION ALL
SELECT 'Trusted records (no open source-quality rule, salary verified)',
       (SELECT count_if(is_trusted) FROM ${schema}.gold_employee_360), NULL;
