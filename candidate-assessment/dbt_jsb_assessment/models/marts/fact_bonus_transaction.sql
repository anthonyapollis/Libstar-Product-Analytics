{{ config(post_hook="{{ table_keys(['player_bonus_id'], indexes=[['player_id'], ['campaign_id']]) }}") }}
-- Grain: one row per player_bonus (grant), with what it has cost so far and what is still owed.
--   bonus_cost        = bonus money from this grant wagered on settled bets (the same definition as
--                       fact_bet.bonus_cost and example_queries.sql (a) and (b))
--   bonus_outstanding = for an active grant, the part not yet wagered: a liability, not yet a cost.
--                       An expired or forfeited remainder is removed from the balance and costs nothing.
with wagered as (
    select player_bonus_id,
           sum(stake_bonus_amount) as bonus_wagered,
           sum(case when status in ('won','lost') then stake_bonus_amount else 0 end) as bonus_cost
    from {{ ref('stg_bets') }}
    where player_bonus_id is not null
    group by player_bonus_id
)
select
    pb.player_bonus_id,
    pb.player_id,
    pb.campaign_id,
    c.campaign_name,
    c.campaign_type,
    pb.granted_amount,
    pb.rollover_required,
    pb.rollover_progress,
    pb.status,
    coalesce(w.bonus_wagered, 0) as bonus_wagered,
    coalesce(w.bonus_cost, 0)    as bonus_cost,
    case when pb.status = 'active' then pb.granted_amount - coalesce(w.bonus_wagered, 0) else 0 end as bonus_outstanding,
    pb.granted_at_utc,
    pb.expires_at_utc,
    pb.resolved_at_utc
from {{ ref('stg_player_bonuses') }} pb
left join wagered w on w.player_bonus_id = pb.player_bonus_id
left join {{ ref('dim_campaign') }} c on c.campaign_id = pb.campaign_id
