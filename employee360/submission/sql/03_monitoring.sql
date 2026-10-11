-- Monitoring table derived from the saved issue detail.
WITH rules AS (
  SELECT * FROM VALUES
    ('DQ01','Uniqueness','Critical','Block release'),
    ('DQ02','Completeness','Medium','Monitor'),
    ('DQ03','Referential integrity','High','Alert now'),
    ('DQ04','Consistency','Critical','Alert now'),
    ('DQ05','Validity','High','Block release'),
    ('DQ06','Timeliness','Medium','Monitor'),
    ('DQ07','Consistency','Critical','Block release'),
    ('RC01','Reconciliation','Critical','Block release'),
    ('RC02','Reconciliation','Critical','Block release'),
    ('RC03','Reconciliation','Critical','Block release')
  AS rules(rule_id, dimension, severity, release_action)
)
SELECT r.rule_id, r.dimension, r.severity, r.release_action,
       COUNT(i.employee_id) AS affected_count,
       CASE WHEN COUNT(i.employee_id) > 0 THEN 'FAIL' ELSE 'PASS' END AS status
FROM rules r LEFT JOIN employee360_dq_issue_detail i ON r.rule_id = i.rule_id
GROUP BY r.rule_id, r.dimension, r.severity, r.release_action
ORDER BY r.rule_id;

-- Release gate: only a failed Block release control blocks publication.
SELECT CASE WHEN SUM(CASE WHEN status = 'FAIL' AND release_action = 'Block release' THEN 1 ELSE 0 END) > 0
            THEN 'BLOCK' ELSE 'PASS' END AS release_decision
FROM employee360_dq_monitoring;
