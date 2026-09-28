select
    run_id,
    source_system,
    started_at,
    finished_at,
    status,
    pages_fetched,
    rows_upserted,
    rows_rejected,
    rate_limit_hits,
    server_error_hits,
    timestampdiff(second, started_at, finished_at) as duration_seconds  -- null while RUNNING
from {{ source('jsb_assessment', 'ingest_runs') }}
