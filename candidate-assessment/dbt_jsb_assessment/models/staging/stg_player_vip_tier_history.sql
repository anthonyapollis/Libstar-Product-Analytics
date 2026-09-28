select
    player_id,
    vip_tier,
    valid_from_utc,
    valid_to_utc,
    valid_to_utc is null as is_current,
    changed_by
from {{ source('jsb_platform', 'player_vip_tier_history') }}
