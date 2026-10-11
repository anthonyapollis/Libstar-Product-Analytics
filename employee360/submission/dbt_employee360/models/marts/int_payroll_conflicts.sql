-- One row per employee/pay period that has more than one salary/currency value.
-- These records are explicitly excluded from arbitrary selection downstream.
select employee_id, pay_period, count(distinct concat(cast(monthly_salary_zar as {{ dbt.type_string() }}), '|', currency)) as distinct_salary_currency_values
from {{ ref('stg_payroll') }}
group by employee_id, pay_period
having count(distinct concat(cast(monthly_salary_zar as {{ dbt.type_string() }}), '|', currency)) > 1

