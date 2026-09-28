-- Grain: one row per accepted bet. Do not combine with fact_wallet_transaction
-- (different grain: a bet is one row here, but produces 1-2 ledger rows --
-- stake and, if it wins, a separate win). See design_notes.md, "three rules".
select
    b.bet_id,
    b.player_id,
    v.vip_tier          as vip_tier_at_bet_time,
    b.product,
    b.channel,
    date(b.placed_at_utc) as placed_date,
    b.stake_real_amount,
    b.stake_bonus_amount,
    b.total_stake,
    b.status,
    b.payout_amount,
    b.ggr_contribution,
    b.placed_at_utc,
    b.settled_at_utc
from {{ ref('stg_bets') }} b
left join {{ ref('dim_player_vip_tier_scd') }} v
    on v.player_id = b.player_id
   and b.placed_at_utc >= v.valid_from_utc
   and b.placed_at_utc <  v.valid_to_utc
