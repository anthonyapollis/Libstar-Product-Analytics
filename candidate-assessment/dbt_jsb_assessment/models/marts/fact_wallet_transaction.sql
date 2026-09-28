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
    status,
    date(created_at_utc) as transaction_date,
    created_at_utc
from {{ ref('stg_wallet_transactions') }}
