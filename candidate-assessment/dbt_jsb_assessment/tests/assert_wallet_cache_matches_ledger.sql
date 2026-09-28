-- The wallets table is only a cache. The append-only ledger is the source of
-- truth. Returns one row per wallet whose cached balance disagrees with the
-- ledger sum (design_notes.md, "How a balance is calculated").
with ledger as (
    select wallet_id,
           sum(case when balance_type = 'real'  then signed_amount else 0 end) as ledger_real,
           sum(case when balance_type = 'bonus' then signed_amount else 0 end) as ledger_bonus
    -- Every row counts: a reversal is its own opposite row, so nothing is filtered out.
    from {{ ref('stg_wallet_transactions') }}
    group by wallet_id
)
select w.wallet_id, w.real_balance, l.ledger_real, w.bonus_balance, l.ledger_bonus
from {{ source('jsb_platform', 'wallets') }} w
left join ledger l on l.wallet_id = w.wallet_id
where abs(w.real_balance  - coalesce(l.ledger_real, 0))  > 0.005
   or abs(w.bonus_balance - coalesce(l.ledger_bonus, 0)) > 0.005
