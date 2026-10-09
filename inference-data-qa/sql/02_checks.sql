-- 2. Executable data-quality checks (Spark SQL). Each check is a view that returns one row per
-- affected record: rule_id, employee_id, source, detail. An empty view means the check passed.

-- DQ01 Uniqueness: employee_id must be unique in every source.
CREATE OR REPLACE TEMP VIEW dq01_uniqueness AS
WITH keyed AS (
  SELECT 'HR' AS source, employee_id, count(*) OVER (PARTITION BY employee_id) AS n FROM stg_hr
  UNION ALL
  SELECT 'Payroll', employee_id, key_count FROM stg_payroll
  UNION ALL
  SELECT 'Employee_360', employee_id, count(*) OVER (PARTITION BY employee_id) FROM stg_e360
)
SELECT DISTINCT 'DQ01' AS rule_id, employee_id, source, concat(n, ' rows for one employee_id') AS detail
FROM keyed WHERE n > 1;

-- DQ02 Completeness: mandatory HR fields are populated. A blank manager is allowed only for the top of
-- the hierarchy, i.e. someone who manages others (assumption: E1001-E1005 are department heads).
CREATE OR REPLACE TEMP VIEW dq02_completeness AS
WITH managers AS (SELECT DISTINCT manager_id AS employee_id FROM stg_hr WHERE manager_id IS NOT NULL),
missing AS (
  SELECT h.employee_id,
         filter(array(
           CASE WHEN h.full_name IS NULL THEN 'full_name' END,
           CASE WHEN h.email IS NULL THEN 'email' END,
           CASE WHEN h.department IS NULL THEN 'department' END,
           CASE WHEN h.location IS NULL THEN 'location' END,
           CASE WHEN h.employment_status IS NULL THEN 'employment_status' END,
           CASE WHEN h.effective_date IS NULL THEN 'effective_date' END,
           CASE WHEN h.manager_id IS NULL AND m.employee_id IS NULL THEN 'manager_id' END
         ), x -> x IS NOT NULL) AS blank_fields
  FROM stg_hr h LEFT JOIN managers m ON m.employee_id = h.employee_id
)
SELECT 'DQ02' AS rule_id, employee_id, 'HR' AS source, concat('blank: ', array_join(blank_fields, ', ')) AS detail
FROM missing WHERE size(blank_fields) > 0;

-- DQ03 Referential integrity: every manager_id must be an employee in HR (checked in HR and Employee 360).
CREATE OR REPLACE TEMP VIEW dq03_manager_exists AS
SELECT 'DQ03' AS rule_id, s.employee_id, s.source, concat('manager_id ', s.manager_id, ' is not in HR') AS detail
FROM (SELECT 'HR' AS source, employee_id, manager_id FROM stg_hr
      UNION ALL SELECT 'Employee_360', employee_id, manager_id FROM stg_e360) s
LEFT ANTI JOIN stg_hr h ON h.employee_id = s.manager_id
WHERE s.manager_id IS NOT NULL;

-- DQ04 Cross-system consistency: HR (owner of employment status) and payroll must agree.
-- Active => exactly one Payable record; Terminated => Stopped. A missing payroll record is also a failure.
CREATE OR REPLACE TEMP VIEW dq04_hr_payroll_status AS
WITH p AS (
  SELECT employee_id, concat_ws('/', collect_set(payroll_status)) AS payroll_status
  FROM stg_payroll GROUP BY employee_id
)
SELECT 'DQ04' AS rule_id, h.employee_id, 'HR vs Payroll' AS source,
       CASE WHEN p.employee_id IS NULL THEN concat('HR ', h.employment_status, ' but no payroll record')
            ELSE concat('HR ', h.employment_status, ', payroll ', p.payroll_status,
                        ' (HR effective ', CAST(h.effective_date AS STRING), ')') END AS detail
FROM stg_hr h LEFT JOIN p ON p.employee_id = h.employee_id
WHERE p.employee_id IS NULL
   OR (h.employment_status = 'Terminated' AND p.payroll_status <> 'Stopped')
   OR (h.employment_status = 'Active'     AND p.payroll_status <> 'Payable');

-- DQ05 Validity: a ZAR salary column holds ZAR, a positive amount, and a well-formed pay period.
CREATE OR REPLACE TEMP VIEW dq05_payroll_validity AS
SELECT 'DQ05' AS rule_id, employee_id, 'Payroll' AS source,
       concat_ws('; ',
         CASE WHEN currency IS NULL OR currency <> 'ZAR' THEN concat('currency ', coalesce(currency, 'blank'), ' in monthly_salary_zar') END,
         CASE WHEN monthly_salary IS NULL OR monthly_salary <= 0 THEN 'salary missing or not positive' END,
         CASE WHEN pay_period IS NULL OR NOT pay_period RLIKE '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN 'bad pay_period' END
       ) AS detail
FROM stg_payroll
WHERE currency IS NULL OR currency <> 'ZAR'
   OR monthly_salary IS NULL OR monthly_salary <= 0
   OR pay_period IS NULL OR NOT pay_period RLIKE '^[0-9]{4}-(0[1-9]|1[0-2])$';

-- DQ06 Freshness: a record not updated in the 30 days before the extract date is stale.
CREATE OR REPLACE TEMP VIEW dq06_freshness AS
SELECT 'DQ06' AS rule_id, employee_id, source,
       concat('last_updated ', CAST(last_updated AS STRING), ', ',
              datediff(DATE'${as_of_date}', last_updated), ' days before the extract') AS detail
FROM (SELECT 'HR' AS source, employee_id, last_updated FROM stg_hr
      UNION ALL SELECT 'Payroll', employee_id, last_updated FROM stg_payroll
      UNION ALL SELECT 'Employee_360', employee_id, last_updated FROM stg_e360)
WHERE last_updated < date_sub(DATE'${as_of_date}', 30);

CREATE OR REPLACE TEMP VIEW dq_check_failures AS
SELECT * FROM dq01_uniqueness
UNION ALL SELECT * FROM dq02_completeness
UNION ALL SELECT * FROM dq03_manager_exists
UNION ALL SELECT * FROM dq04_hr_payroll_status
UNION ALL SELECT * FROM dq05_payroll_validity
UNION ALL SELECT * FROM dq06_freshness;

SELECT rule_id, employee_id, source, detail FROM dq_check_failures ORDER BY rule_id, employee_id, source;
