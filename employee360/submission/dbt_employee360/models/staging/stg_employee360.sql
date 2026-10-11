select
  trim(employee_id) as employee_id,
  full_name,
  department,
  location,
  nullif(trim(manager_id), '') as manager_id,
  employment_status,
  cast(monthly_salary_zar as decimal(18,2)) as monthly_salary_zar,
  currency,
  cast(effective_date as date) as effective_date,
  cast(last_updated as date) as last_updated
from {{ source('raw', 'employee_360') }}
