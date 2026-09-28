select
    player_bonus_id,
    player_id,
    campaign_id,
    granted_amount,
    rollover_required,
    rollover_progress,
    status,
    granted_at_utc,
    expires_at_utc,
    resolved_at_utc
from {{ source('jsb_platform', 'player_bonuses') }}
