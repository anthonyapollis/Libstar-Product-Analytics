-- Exercise 2: correctness checks to run after any ingestion run.
USE jsb_assessment;

-- 1. No duplicates: row count must equal distinct id count.
SELECT COUNT(*) AS row_count, COUNT(DISTINCT id) AS distinct_ids,
       COUNT(*) - COUNT(DISTINCT id) AS duplicate_rows
FROM transactions;

-- 2. Nothing lost silently: every rejected record is still retrievable.
SELECT reason, COUNT(*) AS n FROM ingest_rejects GROUP BY reason;

-- 3. Coverage: every id the provider has is either loaded or quarantined. The full id-by-id
--    comparison needs the API, so it lives in verify_against_api.py; this is the database side.
SELECT (SELECT COUNT(*) FROM transactions) AS loaded,
       (SELECT COUNT(DISTINCT record_id) FROM ingest_rejects
         WHERE record_id NOT IN (SELECT id FROM transactions)) AS quarantined_only,
       (SELECT COUNT(*) FROM transactions)
     + (SELECT COUNT(DISTINCT record_id) FROM ingest_rejects
         WHERE record_id NOT IN (SELECT id FROM transactions)) AS accounted_for;

-- 3b. Rejects are stored once per distinct bad payload (must return no rows).
SELECT payload_sha256, COUNT(*) FROM ingest_rejects GROUP BY payload_sha256 HAVING COUNT(*) > 1;

-- 4. Monitoring: run history, most recent first. New vs changed shows the incremental load working.
SELECT run_id, status, started_at, finished_at,
       TIMESTAMPDIFF(SECOND, started_at, finished_at) AS duration_seconds,
       pages_fetched, rows_new, rows_changed, rows_unchanged, rows_rejected,
       rate_limit_hits, server_error_hits, error_message
FROM ingest_runs
ORDER BY run_id DESC;

-- 5. Alerts. A run still RUNNING after one scheduling interval died without finishing (the next
--    run marks it ABANDONED). A FAILED run means retries were exhausted. Both should page on-call;
--    the data is still safe, because the checkpoint only covers committed pages.
SELECT run_id, status, started_at, TIMESTAMPDIFF(MINUTE, started_at, NOW()) AS minutes_ago, error_message
FROM ingest_runs
WHERE (status = 'RUNNING' AND started_at < NOW() - INTERVAL 5 MINUTE)
   OR status IN ('FAILED', 'ABANDONED')
ORDER BY run_id DESC;

-- 6. Last successful position: what the next run resumes from.
SELECT * FROM ingest_checkpoint;
