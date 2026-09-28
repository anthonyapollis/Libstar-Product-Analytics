-- Exercise 2's ingested table. ingest.py owns extraction/load (dbt is a T-only
-- tool and has no business doing incremental API pagination); this view just
-- gives the loaded data the same staging-layer treatment as the other two
-- exercises, so downstream consumers have one consistent place to look.
select
    id,
    player_id,
    type,
    amount,
    currency,
    status,
    updated_at,
    source_system,
    ingested_at
from {{ source('jsb_assessment', 'transactions') }}
