select
    campaign_id,
    name,
    campaign_type,
    rollover_multiple,
    min_odds,
    max_stake_while_active,
    expiry_days,
    valid_from_utc,
    valid_to_utc
from {{ source('jsb_platform', 'bonus_campaigns') }}
