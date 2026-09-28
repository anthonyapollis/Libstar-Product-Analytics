{{ config(post_hook="{{ table_keys(['product', 'month_start']) }}") }}
-- Reusable version of example_queries.sql query (a): NGR by product, by month of settlement.
-- GGR = stakes - payouts on settled bets; bonus cost = bonus money wagered; NGR = GGR - bonus cost.
select
    product,
    date_format(settled_at_utc, '%Y-%m-01') as month_start,
    sum(total_stake)        as turnover,
    sum(payout_amount)      as payouts,
    sum(ggr_contribution)   as ggr,
    sum(bonus_cost)         as bonus_cost,
    sum(ngr_contribution)   as ngr
from {{ ref('fact_bet') }}
where status in ('won','lost')
group by product, date_format(settled_at_utc, '%Y-%m-01')
