select
    row_id,
    gateway_txn_id,
    merchant_ref,
    settled_at,
    gross_amount,
    fee,
    net_amount,
    currency,
    status,
    upper(regexp_replace(merchant_ref, '[^A-Za-z0-9]', '')) as merchant_ref_norm
from {{ source('jsb_assessment', 'gateway_settlement') }}
