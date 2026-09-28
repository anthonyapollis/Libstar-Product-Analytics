select
    deposit_attempt_id,
    player_id,
    method_id,
    amount,
    currency,
    gateway_ref,
    status,
    created_at_utc,
    settled_at_utc
from {{ source('jsb_platform', 'deposit_attempts') }}
