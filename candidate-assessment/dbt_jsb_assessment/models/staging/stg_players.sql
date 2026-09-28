select
    player_id,
    kyc_status,
    vip_tier            as current_vip_tier,
    status,
    traffic_source,
    affiliate_id,
    preferred_currency,
    registered_at_utc,
    updated_at_utc
from {{ source('jsb_platform', 'players') }}
