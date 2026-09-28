-- The bridge from summary.md as rows, one per step, so a report can draw it as a
-- waterfall: start at the internal total, add or subtract each explained
-- difference, and the running total ends at the gateway total. gateway_settled_total
-- is repeated on every row so a report can show the residual (it must be 0.00;
-- tests/assert_recon_bridge_reconciles.sql enforces that in the build).
with f as (select * from {{ ref('fct_recon_exceptions') }}),
dep_ranked as (
    select amount, row_number() over (partition by gateway_ref_norm order by deposit_id) as rn
    from {{ ref('stg_internal_deposits') }} where status = 'SUCCESS'
),
gw_ranked as (
    select gross_amount, row_number() over (partition by merchant_ref_norm order by row_id) as rn
    from {{ ref('stg_gateway_settlement') }}
),
steps as (
    select 1 as step_order, 'Internal SUCCESS deposits' as step,
           (select sum(amount) from {{ ref('stg_internal_deposits') }} where status = 'SUCCESS') as amount
    union all select 2, 'Duplicate internal deposits', -(select coalesce(sum(amount), 0) from dep_ranked where rn > 1)
    union all select 3, 'Reversals', -(select coalesce(sum(financial_impact), 0) from f where category like 'REVERSAL%')
    union all select 4, 'Not yet settled', -(select coalesce(sum(financial_impact), 0) from f where category = 'BREAK: deposit SUCCESS, no gateway settlement found')
    union all select 5, 'Settles next period', -(select coalesce(sum(financial_impact), 0) from f where category = 'TIMING: settlement expected in next period (created near cut-off)')
    union all select 6, 'Prior-period deposits', (select coalesce(sum(financial_impact), 0) from f where category = 'TIMING: prior-period deposit settled at start of period')
    union all select 7, 'Unrecognised settlements', (select coalesce(sum(financial_impact), 0) from f where category like 'BREAK: unrecognised%')
    union all select 8, 'Settled but marked FAILED', (select coalesce(sum(financial_impact), 0) from f where category like 'BREAK: payment confirmed%')
    union all select 9, 'Duplicate gateway rows', (select coalesce(sum(gross_amount), 0) from gw_ranked where rn > 1)
    union all select 10, 'Gross amount differences', (select coalesce(sum(gross_amount - dep_amount), 0) from f
                                                     where category = 'BREAK: settled gross amount differs from internal amount')
    union all select 11, 'Rounding', (select coalesce(sum(gross_amount - dep_amount), 0) from f where category like 'NOT A PROBLEM%')
)
select
    step_order,
    step,
    round(amount, 2) as amount,
    (select round(sum(gross_amount), 2) from {{ ref('stg_gateway_settlement') }} where status = 'SETTLED') as gateway_settled_total
from steps
