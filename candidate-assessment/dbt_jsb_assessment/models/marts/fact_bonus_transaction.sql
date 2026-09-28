-- Grain: one row per player_bonus (grant), enriched with campaign and realised
-- cost. This is what example_queries.sql query (b) becomes as a reusable model.
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
    pb.realised_bonus_cost,
    pb.granted_at_utc,
    pb.expires_at_utc,
    pb.resolved_at_utc
from {{ ref('stg_player_bonuses') }} pb
left join {{ ref('dim_campaign') }} c on c.campaign_id = pb.campaign_id
