-- Reusable version of example_queries.sql query (a): NGR by product, by month.
with product_ggr as (
    select
        product,
        date_format(settled_at_utc, '%Y-%m-01') as month_start,
        sum(total_stake)      as turnover,
        sum(payout_amount)    as payouts,
        sum(total_stake) - sum(payout_amount) as ggr
    from {{ ref('fact_bet') }}
    where status in ('won','lost')
    group by product, date_format(settled_at_utc, '%Y-%m-01')
),
product_bonus_cost as (
    select
        b.product,
        date_format(b.settled_at_utc, '%Y-%m-01') as month_start,
        sum(w.amount) as bonus_cost
    from {{ ref('fact_wallet_transaction') }} w
    join {{ ref('fact_bet') }} b on b.bet_id = w.related_bet_id
    where w.txn_type = 'bet_stake' and w.balance_type = 'bonus' and b.status = 'lost'
    group by b.product, date_format(b.settled_at_utc, '%Y-%m-01')
)
select
    g.product, g.month_start, g.turnover, g.payouts, g.ggr,
    coalesce(c.bonus_cost, 0) as bonus_cost,
    g.ggr - coalesce(c.bonus_cost, 0) as ngr
from product_ggr g
left join product_bonus_cost c on c.product = g.product and c.month_start = g.month_start
