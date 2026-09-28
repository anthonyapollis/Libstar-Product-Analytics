{{ config(post_hook="{{ table_keys(['bet_id'], indexes=[['player_id'], ['placed_date'], ['product', 'placed_date'], ['campaign_id']]) }}") }}
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
    b.player_bonus_id,
    pb.campaign_id,                                   -- campaign whose bonus paid stake_bonus_amount
    b.status,
    b.payout_amount,
    b.ggr_contribution,
    -- Settled bets only (won/lost). Bonus cost = the bonus money wagered; NGR = GGR - bonus cost
    -- (example_queries.sql and design_notes.md, section 6, give the reasoning).
    case when b.status in ('won','lost') then b.stake_bonus_amount else 0 end as bonus_cost,
    case when b.status in ('won','lost') then b.ggr_contribution - b.stake_bonus_amount else 0 end as ngr_contribution,
    b.placed_at_utc,
    b.settled_at_utc
from {{ ref('stg_bets') }} b
left join {{ ref('stg_player_bonuses') }} pb on pb.player_bonus_id = b.player_bonus_id
left join {{ ref('dim_player_vip_tier_scd') }} v
    on v.player_id = b.player_id
   and b.placed_at_utc >= v.valid_from_utc
   and b.placed_at_utc <  v.valid_to_utc
