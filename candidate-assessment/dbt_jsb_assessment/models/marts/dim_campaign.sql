select
    campaign_id,
    name        as campaign_name,
    campaign_type,
    rollover_multiple,
    min_odds,
    valid_from_utc,
    valid_to_utc
from {{ ref('stg_bonus_campaigns') }}
