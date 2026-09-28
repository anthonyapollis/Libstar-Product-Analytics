-- Exercise 2: correctness checks to run after any ingestion run.
USE jsb_assessment;

-- 1. No duplicates: row count must equal distinct id count.
SELECT COUNT(*) AS row_count, COUNT(DISTINCT id) AS distinct_ids,
       COUNT(*) - COUNT(DISTINCT id) AS duplicate_rows
FROM transactions;

-- 2. Nothing lost silently: every rejected record is still retrievable.
SELECT reason, COUNT(*) AS n FROM ingest_rejects GROUP BY reason;

-- 3. Coverage: loaded + rejected should account for everything the provider has
--    ever returned for a given id (spot-check against a known id / count).
SELECT (SELECT COUNT(*) FROM transactions) + (SELECT COUNT(DISTINCT record_id) FROM ingest_rejects) AS accounted_for;

-- 4. Monitoring: run history, most recent first.
SELECT run_id, source_system, started_at, finished_at, status,
       pages_fetched, rows_upserted, rows_rejected, rate_limit_hits, server_error_hits,
       TIMESTAMPDIFF(SECOND, started_at, COALESCE(finished_at, NOW())) AS duration_seconds
FROM ingest_runs
ORDER BY run_id DESC;

-- 5. Stale-run alert: a run stuck RUNNING for longer than one scheduling
--    interval means the process died without a chance to update its own
--    status (e.g. SIGKILL, host crash) -- this is what should page on-call,
--    since the checkpoint itself is still safe to resume from.
SELECT run_id, started_at, TIMESTAMPDIFF(MINUTE, started_at, NOW()) AS minutes_running
FROM ingest_runs
WHERE status = 'RUNNING' AND started_at < NOW() - INTERVAL 5 MINUTE;

-- 6. Current checkpoint (what the next run will resume from).
SELECT * FROM ingest_checkpoint;
