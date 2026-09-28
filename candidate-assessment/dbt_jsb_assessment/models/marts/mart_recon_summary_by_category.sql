{{ config(post_hook="{{ table_keys(['category']) }}") }}
-- The daily close-pack summary: exception count and total financial impact
-- per category. Reusable version of exercise1-reconciliation/sql/03_reconciliation.sql's
-- query 4 -- what a scheduled dbt run would refresh every morning.
select
    category,
    count(*) as n,
    round(sum(financial_impact), 2) as impact_total
from {{ ref('fct_recon_exceptions') }}
group by category
order by n desc
