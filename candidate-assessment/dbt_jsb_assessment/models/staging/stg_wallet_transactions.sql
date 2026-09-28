-- Grain: one row per wallet ledger movement. This is the spine of financial
-- reporting and reconciliation -- see design_notes.md's "how a balance is
-- calculated" for why this table, not wallets.*_balance, is the source of truth.
select
    wallet_txn_id,
    wallet_id,
    player_id,
    txn_type,
    balance_type,
    amount,
    direction,
    case when direction = 'credit' then amount else -amount end as signed_amount,
    balance_before,
    balance_after,
    related_deposit_attempt_id,
    related_withdrawal_id,
    related_bet_id,
    related_player_bonus_id,
    reversal_of_wallet_txn_id,
    idempotency_key,
    source_system,
    reason,
    created_by,
    created_at_utc,
    ingested_at_utc
from {{ source('jsb_platform', 'wallet_transactions') }}
