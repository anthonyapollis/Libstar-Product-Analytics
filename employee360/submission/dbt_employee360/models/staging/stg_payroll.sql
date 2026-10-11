select
  trim(employee_id) as employee_id,
  payroll_status,
  cast(monthly_salary_zar as decimal(18,2)) as monthly_salary_zar,
  currency,
  pay_period,
  cast(last_updated as date) as last_updated
from {{ source('raw', 'payroll_source') }}
