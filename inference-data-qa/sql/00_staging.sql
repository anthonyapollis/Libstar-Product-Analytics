-- Typed staging views over the three raw extracts (Spark SQL).
-- The raw views raw_hr, raw_payroll and raw_e360 hold every column as a string, exactly as delivered;
-- typing happens here so a bad value is visible instead of silently becoming NULL on load.
-- Parameters (set by the notebook): ${as_of_date} = extract date, ${snapshot_end} = last day of the
-- reporting month.

CREATE OR REPLACE TEMP VIEW stg_hr AS
SELECT
  trim(employee_id)                                   AS employee_id,
  nullif(trim(full_name), '')                         AS full_name,
  nullif(trim(email), '')                             AS email,
  nullif(trim(department), '')                        AS department,
  nullif(trim(location), '')                          AS location_raw,
  -- "CPT" and "Cape Town" are the same place: compare on the standard name, keep the raw value.
  CASE WHEN upper(trim(location)) IN ('CPT', 'CAPE TOWN') THEN 'Cape Town'
       ELSE nullif(trim(location), '') END            AS location,
  nullif(trim(manager_id), '')                        AS manager_id,
  nullif(trim(employment_status), '')                 AS employment_status,
  to_date(effective_date, 'yyyy/MM/dd')               AS effective_date,
  to_date(last_updated, 'yyyy/MM/dd')                 AS last_updated,
  effective_date                                      AS effective_date_raw
FROM raw_hr;

CREATE OR REPLACE TEMP VIEW stg_payroll AS
SELECT
  trim(employee_id)                                   AS employee_id,
  nullif(trim(payroll_status), '')                    AS payroll_status,
  CAST(monthly_salary_zar AS DECIMAL(12, 2))          AS monthly_salary,
  nullif(trim(currency), '')                          AS currency,
  nullif(trim(pay_period), '')                        AS pay_period,
  to_date(last_updated, 'yyyy-MM-dd')                 AS last_updated,
  -- Position in the file, so a duplicate key can be shown in delivery order.
  row_number() OVER (PARTITION BY trim(employee_id) ORDER BY CAST(_line AS INT)) AS key_occurrence,
  count(*)     OVER (PARTITION BY trim(employee_id))                           AS key_count
FROM raw_payroll;

CREATE OR REPLACE TEMP VIEW stg_e360 AS
SELECT
  trim(employee_id)                                   AS employee_id,
  nullif(trim(full_name), '')                         AS full_name,
  nullif(trim(department), '')                        AS department,
  CASE WHEN upper(trim(location)) IN ('CPT', 'CAPE TOWN') THEN 'Cape Town'
       ELSE nullif(trim(location), '') END            AS location,
  nullif(trim(manager_id), '')                        AS manager_id,
  nullif(trim(employment_status), '')                 AS employment_status,
  CAST(monthly_salary_zar AS DECIMAL(12, 2))          AS monthly_salary,
  nullif(trim(currency), '')                          AS currency,
  to_date(effective_date, 'yyyy-MM-dd')               AS effective_date,
  to_date(last_updated, 'yyyy-MM-dd')                 AS last_updated
FROM raw_e360;
