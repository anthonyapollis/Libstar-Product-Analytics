{{ config(post_hook="{{ table_keys(['campaign_name', 'month_start']) }}") }}
-- Reusable version of example_queries.sql query (b): bonus cost as % of NGR, by campaign and month.
-- A bet's bonus stake is charged to the campaign of the grant that paid it (fact_bet.campaign_id).
with campaign_cost as (
    select
        c.campaign_id, c.campaign_name,
        date_format(b.settled_at_utc, '%Y-%m-01') as month_start,
        sum(b.bonus_cost) as bonus_cost
    from {{ ref('fact_bet') }} b
    join {{ ref('dim_campaign') }} c on c.campaign_id = b.campaign_id
    where b.status in ('won','lost')
    group by c.campaign_id, c.campaign_name, date_format(b.settled_at_utc, '%Y-%m-01')
),
period_ngr as (
    select month_start, sum(ngr) as total_ngr
    from {{ ref('mart_ngr_by_product_monthly') }}
    group by month_start
)
select
    cc.campaign_name, cc.month_start, cc.bonus_cost, n.total_ngr,
    round(100 * cc.bonus_cost / nullif(n.total_ngr, 0), 2) as bonus_cost_pct_of_ngr
from campaign_cost cc
left join period_ngr n on n.month_start = cc.month_start
