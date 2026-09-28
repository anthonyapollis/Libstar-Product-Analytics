-- Singular test: the internal-total -> gateway-total bridge from summary.md
-- must reconcile to zero residual, enforced in SQL rather than just verified
-- once by hand. Fails (returns a row) if the residual exceeds 2 cents.
with dep_ranked as (
    select deposit_id, gateway_ref_norm, amount,
           row_number() over (partition by gateway_ref_norm order by deposit_id) as rn
    from {{ ref('stg_internal_deposits') }}
    where status = 'SUCCESS'
),
dup_internal_excess as (
    select coalesce(sum(amount), 0) as v from dep_ranked where rn > 1
),
gw_ranked as (
    select row_id, merchant_ref_norm, gross_amount,
           row_number() over (partition by merchant_ref_norm order by row_id) as rn
    from {{ ref('stg_gateway_settlement') }}
),
dup_gateway_excess as (
    select coalesce(sum(gross_amount), 0) as v from gw_ranked where rn > 1
),
reversals as (
    select coalesce(sum(financial_impact), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category like 'REVERSAL%'
),
missing as (
    select coalesce(sum(financial_impact), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category = 'BREAK: deposit SUCCESS, no gateway settlement found'
),
timing as (
    select coalesce(sum(financial_impact), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category = 'TIMING: settlement expected in next period (created near cut-off)'
),
prior_period as (
    select coalesce(sum(financial_impact), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category = 'TIMING: prior-period deposit settled at start of period'
),
unrecognised as (
    select coalesce(sum(financial_impact), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category like 'BREAK: unrecognised%'
),
failed_settled as (
    select coalesce(sum(financial_impact), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category like 'BREAK: payment confirmed%'
),
amount_net as (
    select coalesce(sum(gross_amount - dep_amount), 0) as v from {{ ref('fct_recon_exceptions') }}
    where category = 'BREAK: settled gross amount differs from internal amount'
       or category like 'NOT A PROBLEM%'
),
totals as (
    select
        (select sum(amount) from {{ ref('stg_internal_deposits') }} where status = 'SUCCESS') as internal_total,
        (select sum(gross_amount) from {{ ref('stg_gateway_settlement') }} where status = 'SETTLED') as gateway_total
)
select
    t.internal_total,
    t.gateway_total,
    t.internal_total
        - (select v from dup_internal_excess) - (select v from reversals)
        - (select v from missing) - (select v from timing)
        + (select v from unrecognised) + (select v from prior_period) + (select v from failed_settled)
        + (select v from dup_gateway_excess) + (select v from amount_net)
        as computed_gateway_total,
    round(
        (t.internal_total
            - (select v from dup_internal_excess) - (select v from reversals)
            - (select v from missing) - (select v from timing)
            + (select v from unrecognised) + (select v from prior_period) + (select v from failed_settled)
            + (select v from dup_gateway_excess) + (select v from amount_net))
        - t.gateway_total, 2) as residual
from totals t
having abs(residual) > 0.02
