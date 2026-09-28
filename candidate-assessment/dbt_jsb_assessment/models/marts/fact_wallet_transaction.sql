{{ config(
    materialized='incremental',
    unique_key='wallet_txn_id',
    post_hook="{{ table_keys(['wallet_txn_id'], unique=[['idempotency_key']], indexes=[['player_id', 'transaction_date'], ['transaction_date']]) }}"
) }}
-- Incremental: the ledger is append-only (a correction is a new reversing row, never an edit),
-- so each run only needs rows with a higher wallet_txn_id than the table already holds.
-- `dbt run --full-refresh` rebuilds it from scratch.
-- Grain: one row per wallet ledger movement -- the spine of reconciliation and
-- finance reporting (mirrors FACT_WALLET_TRANSACTION in the platform ebook).
select
    wallet_txn_id,
    wallet_id,
    player_id,
    txn_type,
    balance_type,
    amount,
    direction,
    signed_amount,
    balance_before,
    balance_after,
    related_bet_id,
    related_deposit_attempt_id,
    related_withdrawal_id,
    related_player_bonus_id,
    reversal_of_wallet_txn_id,
    idempotency_key,
    source_system,
    date(created_at_utc) as transaction_date,
    created_at_utc
from {{ ref('stg_wallet_transactions') }}
{% if is_incremental() %}
where wallet_txn_id > (select coalesce(max(wallet_txn_id), 0) from {{ this }})
{% endif %}
