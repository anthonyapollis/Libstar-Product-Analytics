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
    resolved_at_utc,
    -- Cost is only realised once the grant resolves; an active grant is a
    -- liability, not yet a cost (see design_notes.md).
    case when status in ('completed','expired','forfeited') then granted_amount else 0 end as realised_bonus_cost
from {{ source('jsb_platform', 'player_bonuses') }}
