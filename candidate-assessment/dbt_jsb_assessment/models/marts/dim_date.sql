-- Small date spine covering the assessment period. A production build would
-- generate this far wider (e.g. 10 years) once, not per-run.
with recursive dates as (
    select date('2026-08-01') as date_day
    union all
    select date_add(date_day, interval 1 day)
    from dates
    where date_day < '2026-10-31'
)
select
    date_day,
    year(date_day)              as year,
    month(date_day)             as month,
    day(date_day)                as day,
    dayname(date_day)           as day_name,
    weekday(date_day) >= 5      as is_weekend
from dates
