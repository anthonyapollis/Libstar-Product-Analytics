-- Exercise 1's reconciliation logic as a dbt model, so it can be scheduled
-- (dbt run, daily) rather than run as a one-off script -- the automation
-- summary.md describes in prose, made real. Same categorisation as
-- exercise1-reconciliation/sql/03_reconciliation.sql; see that file's
-- comments for the reasoning behind each category. Ported to plain CTEs
-- (no TEMPORARY TABLEs) since a dbt model is just one query.
with dep_dupe_flag as (
    select deposit_id, gateway_ref_norm,
           count(*) over (partition by gateway_ref_norm) as dep_ref_count
    from {{ ref('stg_internal_deposits') }}
    where status = 'SUCCESS'
),
gw_dupe_flag as (
    select row_id, merchant_ref_norm,
           count(*) over (partition by merchant_ref_norm) as gw_ref_count
    from {{ ref('stg_gateway_settlement') }}
),
matched as (
    select
        d.deposit_id, d.player_id, d.created_at, d.amount as dep_amount,
        d.gateway_ref, d.status as dep_status,
        g.row_id as settlement_row_id, g.gateway_txn_id, g.merchant_ref, g.settled_at,
        g.gross_amount, g.fee, g.net_amount, g.status as gw_status,
        ddf.dep_ref_count, gdf.gw_ref_count
    from {{ ref('stg_internal_deposits') }} d
    left join {{ ref('stg_gateway_settlement') }} g on g.merchant_ref_norm = d.gateway_ref_norm
    left join dep_dupe_flag ddf on ddf.deposit_id = d.deposit_id
    left join gw_dupe_flag gdf on gdf.row_id = g.row_id
    where d.status = 'SUCCESS'

    union all

    -- Settlement rows not matched to any SUCCESS deposit above: either they
    -- belong to a FAILED deposit, or there is no internal record at all.
    select
        d2.deposit_id, d2.player_id, d2.created_at, d2.amount, g.merchant_ref, d2.status,
        g.row_id, g.gateway_txn_id, g.merchant_ref, g.settled_at,
        g.gross_amount, g.fee, g.net_amount, g.status,
        null, gdf.gw_ref_count
    from {{ ref('stg_gateway_settlement') }} g
    left join gw_dupe_flag gdf on gdf.row_id = g.row_id
    left join {{ ref('stg_internal_deposits') }} d2 on d2.gateway_ref_norm = g.merchant_ref_norm
    where not exists (
        select 1 from {{ ref('stg_internal_deposits') }} d
        where d.gateway_ref_norm = g.merchant_ref_norm and d.status = 'SUCCESS'
    )
),
categorised as (
select
    deposit_id, player_id, created_at, dep_amount, gateway_ref,
    settlement_row_id, gateway_txn_id, merchant_ref, settled_at,
    gross_amount, fee, net_amount, gw_status,
    round(gross_amount * 0.02 + 1.00, 2) as expected_fee,
    case
        when dep_status = 'FAILED' and gw_status = 'SETTLED'
            then 'BREAK: payment confirmed, wallet not credited'
        when deposit_id is null and gw_status = 'SETTLED' and settled_at < '2026-09-01 00:15:00'
            then 'TIMING: prior-period deposit settled at start of period'
        when deposit_id is null and gw_status = 'SETTLED'
            then 'BREAK: unrecognised settlement (no internal record)'
        when dep_ref_count > 1
            then 'BREAK: duplicate internal SUCCESS deposit for one settlement (double-credit risk)'
        when gw_ref_count > 1
            then 'BREAK: duplicate gateway settlement for one reference (double-credit risk)'
        when settlement_row_id is null and created_at >= '2026-09-07 23:45:00'
            then 'TIMING: settlement expected in next period (created near cut-off)'
        when settlement_row_id is null
            then 'BREAK: deposit SUCCESS, no gateway settlement found'
        when gw_status = 'REVERSED'
            then 'REVERSAL: gateway reversed/charged back after settlement'
        when abs(fee - round(gross_amount * 0.02 + 1.00, 2)) > 0.02
            then 'BREAK: settled fee differs from contracted fee'
        when abs(net_amount - (gross_amount - fee)) > 0.005
            then 'BREAK: net amount is not gross minus fee'
        when abs(dep_amount - gross_amount) > 0.02
            then 'BREAK: settled gross amount differs from internal amount'
        when abs(dep_amount - gross_amount) between 0.005 and 0.02
            then 'NOT A PROBLEM: rounding difference <= 1 cent'
        else 'OK: matched, amount and fee correct'
    end as category,
    case
        when dep_status = 'FAILED' and gw_status = 'SETTLED' then gross_amount
        when deposit_id is null and gw_status = 'SETTLED' then gross_amount
        when settlement_row_id is null then dep_amount
        when gw_status = 'REVERSED' then gross_amount
        when abs(fee - round(gross_amount * 0.02 + 1.00, 2)) > 0.02
            then round(fee - round(gross_amount * 0.02 + 1.00, 2), 2)
        when abs(net_amount - (gross_amount - fee)) > 0.005
            then round((gross_amount - fee) - net_amount, 2)
        else round(coalesce(dep_amount, 0) - coalesce(gross_amount, 0), 2)
    end as financial_impact
from matched
)
select
    categorised.*,
    substring_index(category, ':', 1) as category_type  -- OK / BREAK / TIMING / REVERSAL / NOT A PROBLEM
from categorised
