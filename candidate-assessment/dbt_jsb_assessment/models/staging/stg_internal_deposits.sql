select
    deposit_id,
    player_id,
    created_at,
    amount,
    currency,
    method,
    gateway_ref,
    status,
    upper(regexp_replace(gateway_ref, '[^A-Za-z0-9]', '')) as gateway_ref_norm
from {{ source('jsb_assessment', 'internal_deposits') }}
