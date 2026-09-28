{{ config(
    materialized='incremental',
    unique_key='id',
    post_hook="{{ table_keys(['id'], indexes=[['updated_at'], ['ingested_at'], ['player_id']]) }}"
) }}
-- Exercise 2's API transactions for reporting: one row per provider id, latest version.
-- Incremental: ingest.py stamps ingested_at whenever it inserts a record or loads a change, so
-- each run only picks up rows stamped after the latest one already here. That is safe without an
-- overlap window: a page commits all at once (its rows share one statement timestamp), and only one
-- ingestion run can hold the lock, so anything committed after dbt last ran is stamped later.
-- A changed record replaces its old row: dbt-mysql deletes and re-inserts by the unique key (id).
select
    id,
    player_id,
    type,
    amount,
    currency,
    status,
    updated_at,
    ingested_at,
    source_system
from {{ ref('stg_transactions') }}
{% if is_incremental() %}
where ingested_at > (select coalesce(max(ingested_at), '1970-01-01') from {{ this }})
{% endif %}
