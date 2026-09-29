-- Proof queries for the Windows / MySQL Workbench captures (evidence/README.md, P2 and P3).
-- Run after local_load/setup_local.bat has finished. Read-only.

-- P2: object count per schema, and in total: expect 6 / 24 / 13 / 11, total 43 tables + 11 views = 54.
SELECT COALESCE(table_schema, 'TOTAL') AS table_schema,
       SUM(table_type = 'BASE TABLE') AS tables,
       SUM(table_type = 'VIEW')       AS views,
       COUNT(*)                       AS objects
FROM information_schema.tables
WHERE table_schema IN ('jsb_assessment', 'jsb_platform', 'jsb_platform_staging', 'jsb_platform_marts')
GROUP BY table_schema WITH ROLLUP;

-- P2: tables without a primary key: expect no rows.
SELECT t.table_schema, t.table_name
FROM information_schema.tables t
LEFT JOIN information_schema.table_constraints c
  ON c.table_schema = t.table_schema AND c.table_name = t.table_name AND c.constraint_type = 'PRIMARY KEY'
WHERE t.table_schema IN ('jsb_assessment', 'jsb_platform', 'jsb_platform_marts')
  AND t.table_type = 'BASE TABLE' AND c.constraint_name IS NULL;

-- P3: reconciliation summary: expect 274 rows categorised OK, 317 rows in total.
SELECT category_type, COUNT(*) AS n_rows
FROM jsb_platform_marts.fct_recon_exceptions
GROUP BY category_type WITH ROLLUP;

-- P3: the bridge: steps from the internal total to the gateway total; residual must be 0.00.
SELECT step_order, step, amount FROM jsb_platform_marts.mart_recon_bridge ORDER BY step_order;
SELECT ROUND(SUM(amount) - MAX(gateway_settled_total), 2) AS bridge_residual
FROM jsb_platform_marts.mart_recon_bridge;
