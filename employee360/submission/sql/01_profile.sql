-- Run in Databricks SQL. Replace catalog.schema placeholders.
-- Profile row count and distinct employee IDs for each source.
SELECT 'HR' AS source, COUNT(*) AS rows, COUNT(DISTINCT employee_id) AS distinct_employee_ids,
       SUM(CASE WHEN employee_id IS NULL THEN 1 ELSE 0 END) AS null_employee_ids
FROM hr_source
UNION ALL
SELECT 'Payroll', COUNT(*), COUNT(DISTINCT employee_id), SUM(CASE WHEN employee_id IS NULL THEN 1 ELSE 0 END) FROM payroll_source
UNION ALL
SELECT 'Employee_360', COUNT(*), COUNT(DISTINCT employee_id), SUM(CASE WHEN employee_id IS NULL THEN 1 ELSE 0 END) FROM employee_360;

-- Duplicate business keys: a failing result is a DQ01 finding.
SELECT 'HR' AS source, employee_id, COUNT(*) AS copies FROM hr_source GROUP BY employee_id HAVING COUNT(*) > 1
UNION ALL SELECT 'Payroll', employee_id, COUNT(*) FROM payroll_source GROUP BY employee_id HAVING COUNT(*) > 1
UNION ALL SELECT 'Employee_360', employee_id, COUNT(*) FROM employee_360 GROUP BY employee_id HAVING COUNT(*) > 1;
