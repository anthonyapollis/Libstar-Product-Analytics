# Expected values in the Power BI report

Computed with pandas straight from `data/*.csv`, independently of the DAX. Open the
report, refresh, and each visual should show exactly these numbers. They also match
`exercise3-schema-design/example_queries.sql` and the dbt marts.

## Page 1: NGR overview

| Visual | Expected |
|---|---|
| Card: GGR | -70.00 |
| Card: Bonus Cost (realised) | 20.00 |
| Card: NGR | -90.00 |
| Card: Bonus Liability Outstanding | 50.00 |
| Column chart, casino: GGR / NGR | -30.00 / -30.00 |
| Column chart, retail: GGR / NGR | 100.00 / 100.00 |
| Column chart, sportsbook: GGR / NGR | -140.00 / -160.00 |
| Table, Registration Bonus: Campaign Bonus Cost / % of NGR | 25.00 / -27.78% |

## Page 2: Player balances

| Date slicer upper bound | Player | Balance type | Expected balance |
|---|---|---|---|
| 2026-09-06 | 1 | real | 1,160.00 |
| 2026-09-06 | 3 | bonus | 30.00 |
| 2026-09-06 | 3 | real | 100.00 |
| 2026-10-31 | 1 | real | 1,190.00 |
| 2026-10-31 | 2 | real | 400.00 |
| 2026-10-31 | 3 | bonus | 30.00 |
| 2026-10-31 | 3 | real | 100.00 |

Card: Deposits (full date range) = 1,600.00
