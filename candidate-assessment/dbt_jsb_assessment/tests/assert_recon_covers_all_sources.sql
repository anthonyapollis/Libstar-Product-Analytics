-- Singular test: every SUCCESS internal deposit and every gateway settlement
-- row must appear in fct_recon_exceptions at least once. A failing row here
-- means the reconciliation silently dropped a source record -- exactly the
-- "control total" check the automation design in summary.md describes,
-- made enforceable instead of just prose.
with missing_deposits as (
    select d.deposit_id
    from {{ ref('stg_internal_deposits') }} d
    where d.status = 'SUCCESS'
      and not exists (
          select 1 from {{ ref('fct_recon_exceptions') }} f
          where f.deposit_id = d.deposit_id
      )
),
missing_settlements as (
    select g.row_id
    from {{ ref('stg_gateway_settlement') }} g
    where not exists (
          select 1 from {{ ref('fct_recon_exceptions') }} f
          where f.settlement_row_id = g.row_id
      )
)
select 'missing_deposit' as issue, deposit_id as source_id from missing_deposits
union all
select 'missing_settlement', cast(row_id as char) from missing_settlements
