-- 1. Profiling (Spark SQL). Each statement is one result set in the notebook.

-- P1. Rows, distinct keys and duplicate keys per source.
SELECT 'HR' AS source, count(*) AS row_count, count(DISTINCT employee_id) AS distinct_ids,
       count(*) - count(DISTINCT employee_id) AS duplicate_rows, min(employee_id) AS min_id, max(employee_id) AS max_id
FROM stg_hr
UNION ALL
SELECT 'Payroll', count(*), count(DISTINCT employee_id), count(*) - count(DISTINCT employee_id), min(employee_id), max(employee_id)
FROM stg_payroll
UNION ALL
SELECT 'Employee_360', count(*), count(DISTINCT employee_id), count(*) - count(DISTINCT employee_id), min(employee_id), max(employee_id)
FROM stg_e360;

-- P2. Null or blank rate for every column that has any (stack() turns columns into rows).
WITH hr AS (
  SELECT stack(9,
    'employee_id', employee_id, 'full_name', full_name, 'email', email, 'department', department,
    'location', location_raw, 'manager_id', manager_id, 'employment_status', employment_status,
    'effective_date', CAST(effective_date AS STRING), 'last_updated', CAST(last_updated AS STRING)
  ) AS (column_name, value) FROM stg_hr
), py AS (
  SELECT stack(6,
    'employee_id', employee_id, 'payroll_status', payroll_status, 'monthly_salary', CAST(monthly_salary AS STRING),
    'currency', currency, 'pay_period', pay_period, 'last_updated', CAST(last_updated AS STRING)
  ) AS (column_name, value) FROM stg_payroll
), e AS (
  SELECT stack(10,
    'employee_id', employee_id, 'full_name', full_name, 'department', department, 'location', location,
    'manager_id', manager_id, 'employment_status', employment_status, 'monthly_salary', CAST(monthly_salary AS STRING),
    'currency', currency, 'effective_date', CAST(effective_date AS STRING), 'last_updated', CAST(last_updated AS STRING)
  ) AS (column_name, value) FROM stg_e360
), all_cols AS (
  SELECT 'HR' AS source, * FROM hr UNION ALL SELECT 'Payroll', * FROM py UNION ALL SELECT 'Employee_360', * FROM e
)
SELECT source, column_name, count(*) AS row_count, sum(CASE WHEN value IS NULL THEN 1 ELSE 0 END) AS null_count,
       round(100.0 * sum(CASE WHEN value IS NULL THEN 1 ELSE 0 END) / count(*), 1) AS null_pct
FROM all_cols
GROUP BY source, column_name
HAVING null_count > 0
ORDER BY source, column_name;

-- P3. Duplicate keys, with the conflicting values side by side.
SELECT employee_id, key_occurrence, key_count, payroll_status, monthly_salary, currency, pay_period, last_updated
FROM stg_payroll
WHERE key_count > 1
ORDER BY employee_id, key_occurrence;

-- P4. Freshness: how old each source is relative to the extract date, and the payroll period.
SELECT 'HR' AS source, min(last_updated) AS oldest_update, max(last_updated) AS newest_update,
       sum(CASE WHEN last_updated < date_sub(DATE'${as_of_date}', 30) THEN 1 ELSE 0 END) AS rows_older_than_30d,
       CAST(NULL AS STRING) AS pay_periods
FROM stg_hr
UNION ALL
SELECT 'Payroll', min(last_updated), max(last_updated),
       sum(CASE WHEN last_updated < date_sub(DATE'${as_of_date}', 30) THEN 1 ELSE 0 END),
       concat_ws(',', collect_set(pay_period))
FROM stg_payroll
UNION ALL
SELECT 'Employee_360', min(last_updated), max(last_updated),
       sum(CASE WHEN last_updated < date_sub(DATE'${as_of_date}', 30) THEN 1 ELSE 0 END), NULL
FROM stg_e360;

-- P5. Unexpected patterns worth a human look (not all of them are errors).
SELECT 'HR dates use yyyy/MM/dd; the other files use ISO yyyy-MM-dd' AS pattern,
       count(*) AS rows_affected, CAST(NULL AS STRING) AS example_ids
FROM stg_hr WHERE effective_date_raw LIKE '____/__/__'
UNION ALL
SELECT 'HR effective_date after the reporting month (future-dated change)', count(*), concat_ws(',', collect_list(employee_id))
FROM stg_hr WHERE effective_date > DATE'${snapshot_end}'
UNION ALL
SELECT 'HR last_updated earlier than effective_date (change keyed in before it takes effect)', count(*), NULL
FROM stg_hr WHERE last_updated < effective_date
UNION ALL
SELECT 'Location alias (CPT for Cape Town)', count(*), concat_ws(',', collect_list(employee_id))
FROM stg_hr WHERE location_raw <> location
UNION ALL
SELECT 'Payroll currency other than ZAR in a ZAR salary column', count(*), concat_ws(',', collect_list(employee_id))
FROM stg_payroll WHERE currency <> 'ZAR'
UNION ALL
SELECT 'Payroll pay_period is not the reporting month', count(*), NULL
FROM stg_payroll WHERE pay_period <> substr('${snapshot_end}', 1, 7);
