-- Conformed dimension: current player attributes only. Point-in-time VIP tier
-- lives in dim_player_vip_tier_scd (Type 2) so "GGR by tier as it stood at bet
-- time" doesn't silently use today's tier for a bet placed months ago.
select
    player_id,
    kyc_status,
    current_vip_tier,
    status,
    traffic_source,
    affiliate_id,
    preferred_currency,
    registered_at_utc
from {{ ref('stg_players') }}
