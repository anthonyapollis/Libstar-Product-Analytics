select
  trim(employee_id) as employee_id,
  full_name,
  nullif(trim(email), '') as email,
  nullif(trim(department), '') as department,
  nullif(trim(manager_id), '') as manager_id,
  employment_status,
  cast(effective_date as date) as effective_date,
  cast(last_updated as date) as last_updated
from {{ source('raw', 'hr_source') }}
