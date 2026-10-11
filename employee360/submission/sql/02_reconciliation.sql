-- Field-level reconciliation. Never use an arbitrary FIRST() after GROUP BY.
WITH payroll_conflicts AS (
  SELECT employee_id
  FROM payroll_source
  GROUP BY employee_id, pay_period
  HAVING COUNT(DISTINCT concat(monthly_salary_zar, '|', currency)) > 1
), payroll_one AS (
  SELECT p.*
  FROM payroll_source p
  LEFT ANTI JOIN payroll_conflicts c USING (employee_id)
), hr_to_e360 AS (
  SELECT h.employee_id, 'Missing downstream' AS category
  FROM hr_source h LEFT ANTI JOIN employee_360 e USING (employee_id)
), e360_to_hr AS (
  SELECT e.employee_id, 'Unexpected downstream' AS category
  FROM employee_360 e LEFT ANTI JOIN hr_source h USING (employee_id)
), cannot_verify AS (
  SELECT employee_id, 'Cannot verify' AS category FROM payroll_conflicts
), field_errors AS (
  SELECT e.employee_id, 'Field error' AS category
  FROM employee_360 e JOIN hr_source h USING (employee_id)
  LEFT JOIN payroll_one p USING (employee_id)
  WHERE h.employment_status <> e.employment_status
     OR p.employee_id IS NULL
     OR p.monthly_salary_zar <> e.monthly_salary_zar
     OR p.currency <> e.currency
)
SELECT * FROM hr_to_e360 UNION ALL SELECT * FROM e360_to_hr UNION ALL
SELECT * FROM cannot_verify UNION ALL SELECT * FROM field_errors;
