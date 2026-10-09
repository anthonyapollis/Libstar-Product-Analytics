-- 3. Source-to-target reconciliation, key level (Spark SQL). The field-level comparison is in PySpark
-- in the notebook (reconcile_fields), because it compares many fields with per-field rules.

-- R1. Key coverage: every employee in HR should be in Employee 360, and nothing else should be.
CREATE OR REPLACE TEMP VIEW recon_keys AS
WITH hr AS (SELECT employee_id, employment_status FROM stg_hr),
py AS (SELECT DISTINCT employee_id FROM stg_payroll),
e  AS (SELECT employee_id, full_name FROM stg_e360)
SELECT coalesce(hr.employee_id, e.employee_id) AS employee_id,
       hr.employee_id IS NOT NULL AS in_hr,
       py.employee_id IS NOT NULL AS in_payroll,
       e.employee_id  IS NOT NULL AS in_e360,
       CASE WHEN e.employee_id IS NULL THEN 'Missing downstream'
            WHEN hr.employee_id IS NULL THEN 'Unexpected downstream'
            ELSE 'Matched' END AS key_status,
       coalesce(e.full_name, (SELECT full_name FROM stg_hr x WHERE x.employee_id = hr.employee_id)) AS full_name
FROM hr
FULL OUTER JOIN e ON e.employee_id = hr.employee_id
LEFT JOIN py ON py.employee_id = coalesce(hr.employee_id, e.employee_id);

SELECT employee_id, full_name, key_status, in_hr, in_payroll, in_e360
FROM recon_keys WHERE key_status <> 'Matched' ORDER BY employee_id;

-- R2. Why matching totals prove nothing: all three files have 48 rows, yet the key sets differ.
SELECT 'Row count' AS measure,
       (SELECT count(*) FROM stg_hr) AS hr, (SELECT count(*) FROM stg_payroll) AS payroll, (SELECT count(*) FROM stg_e360) AS employee_360
UNION ALL
SELECT 'Distinct employee_id',
       (SELECT count(DISTINCT employee_id) FROM stg_hr), (SELECT count(DISTINCT employee_id) FROM stg_payroll),
       (SELECT count(DISTINCT employee_id) FROM stg_e360)
UNION ALL
SELECT 'IDs also in HR',
       (SELECT count(*) FROM stg_hr),
       (SELECT count(DISTINCT p.employee_id) FROM stg_payroll p LEFT SEMI JOIN stg_hr h ON h.employee_id = p.employee_id),
       (SELECT count(*) FROM stg_e360 e LEFT SEMI JOIN stg_hr h ON h.employee_id = e.employee_id);

-- R3. The same point with money. A net salary difference looks like one modest gap, but it is the sum
-- of errors that partly cancel out. Gross (absolute) difference per employee shows the real exposure.
WITH p AS (SELECT employee_id, monthly_salary FROM stg_payroll WHERE key_occurrence = 1),
d AS (
  SELECT coalesce(p.employee_id, e.employee_id) AS employee_id,
         coalesce(e.monthly_salary, 0) - coalesce(p.monthly_salary, 0) AS diff
  FROM p FULL OUTER JOIN stg_e360 e ON e.employee_id = p.employee_id
)
SELECT (SELECT sum(monthly_salary) FROM p)        AS payroll_total,
       (SELECT sum(monthly_salary) FROM stg_e360) AS e360_total,
       sum(diff)                                  AS net_difference,
       sum(abs(diff))                             AS gross_difference,
       count_if(diff <> 0)                        AS employees_with_a_difference,
       concat_ws(', ', collect_list(CASE WHEN diff <> 0 THEN concat(employee_id, ' ', CAST(diff AS STRING)) END)) AS by_employee
FROM d;

-- R4. Evidence for the root-cause note: is each unexpected Employee 360 record a copy of a real one?
-- Compares every non-key attribute of the unexpected record with every other Employee 360 record.
WITH unexpected AS (SELECT e.* FROM stg_e360 e LEFT ANTI JOIN stg_hr h ON h.employee_id = e.employee_id),
scored AS (
  SELECT u.employee_id AS unexpected_id, u.full_name AS unexpected_name,
         o.employee_id AS lookalike_id, o.full_name AS lookalike_name,
         (CASE WHEN u.department        <=> o.department        THEN 1 ELSE 0 END
        + CASE WHEN u.location          <=> o.location          THEN 1 ELSE 0 END
        + CASE WHEN u.manager_id        <=> o.manager_id        THEN 1 ELSE 0 END
        + CASE WHEN u.employment_status <=> o.employment_status THEN 1 ELSE 0 END
        + CASE WHEN u.monthly_salary    <=> o.monthly_salary    THEN 1 ELSE 0 END
        + CASE WHEN u.currency          <=> o.currency          THEN 1 ELSE 0 END
        + CASE WHEN u.effective_date    <=> o.effective_date    THEN 1 ELSE 0 END
        + CASE WHEN u.last_updated      <=> o.last_updated      THEN 1 ELSE 0 END) AS attributes_equal_of_8,
         o.department, o.location, o.manager_id, o.monthly_salary, o.effective_date
  FROM unexpected u JOIN stg_e360 o ON o.employee_id <> u.employee_id
)
-- (QUALIFY would be shorter on Databricks, but open-source Spark does not support it.)
SELECT * EXCEPT (rnk) FROM (
  SELECT *, rank() OVER (PARTITION BY unexpected_id ORDER BY attributes_equal_of_8 DESC) AS rnk FROM scored
) WHERE rnk = 1
ORDER BY unexpected_id, lookalike_id;
