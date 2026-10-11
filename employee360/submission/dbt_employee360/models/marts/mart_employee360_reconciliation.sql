-- Current Employee 360 reconciliation mart. Payroll remains at employee_id + pay_period grain.
with current_pay_period as (
  select max(pay_period) as pay_period from {{ ref('stg_payroll') }}
), payroll_current as (
  select p.*
  from {{ ref('stg_payroll') }} p
  inner join current_pay_period c on p.pay_period = c.pay_period
  left join {{ ref('int_payroll_conflicts') }} conflict
    on p.employee_id = conflict.employee_id and p.pay_period = conflict.pay_period
  where conflict.employee_id is null
), reconciled as (
  select
    h.employee_id,
    h.full_name as hr_full_name,
    h.department as hr_department,
    h.employment_status as hr_status,
    p.monthly_salary_zar as payroll_salary_zar,
    p.currency as payroll_currency,
    e.full_name as employee360_full_name,
    e.department as employee360_department,
    e.employment_status as employee360_status,
    e.monthly_salary_zar as employee360_salary_zar,
    e.currency as employee360_currency,
    case
      when e.employee_id is null then 'MISSING_DOWNSTREAM'
      when h.employment_status <> e.employment_status then 'FIELD_ERROR'
      when p.employee_id is null then 'CANNOT_VERIFY'
      when p.monthly_salary_zar <> e.monthly_salary_zar or p.currency <> e.currency then 'FIELD_ERROR'
      else 'TRUSTED'
    end as reconciliation_status
  from {{ ref('stg_hr') }} h
  left join payroll_current p on h.employee_id = p.employee_id
  left join {{ ref('stg_employee360') }} e on h.employee_id = e.employee_id
)
select * from reconciled
