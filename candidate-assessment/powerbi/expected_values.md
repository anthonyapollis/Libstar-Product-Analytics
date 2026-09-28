# Expected values in the Power BI report

Computed with pandas straight from `data/*.csv`, independently of the DAX. After a
refresh, each visual should show exactly these numbers. They also match
`exercise3-schema-design/example_queries.sql`, `exercise1-reconciliation/summary.md`
and the dbt marts.

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

| Date slicer end | Player | Balance type | Expected balance |
|---|---|---|---|
| 2026-09-06 | 1 | real | 1,160.00 |
| 2026-09-06 | 3 | bonus | 30.00 |
| 2026-09-06 | 3 | real | 100.00 |
| 2026-10-31 | 1 | real | 1,190.00 |
| 2026-10-31 | 2 | real | 400.00 |
| 2026-10-31 | 3 | bonus | 30.00 |
| 2026-10-31 | 3 | real | 100.00 |
| Card: Deposits (full range) | | | 1,600.00 |

## Page 3: Reconciliation

| Visual | Expected |
|---|---|
| Card: Settlements Matched Exactly | 274 |
| Card: Exceptions | 43 |
| Card: Act Now Value | 3,150.00 |
| Card: Bridge Residual | 0.00 |
| Waterfall step 1: Internal SUCCESS deposits | 218,280.00 (running 218,280.00) |
| Waterfall step 2: Duplicate internal deposits | -1,300.00 (running 216,980.00) |
| Waterfall step 3: Reversals | -850.00 (running 216,130.00) |
| Waterfall step 4: Not yet settled | -2,700.00 (running 213,430.00) |
| Waterfall step 5: Settles next period | -3,650.00 (running 209,780.00) |
| Waterfall step 6: Prior-period deposits | 2,600.00 (running 212,380.00) |
| Waterfall step 7: Unrecognised settlements | 2,900.00 (running 215,280.00) |
| Waterfall step 8: Settled but marked FAILED | 250.00 (running 215,530.00) |
| Waterfall step 9: Duplicate gateway rows | 1,550.00 (running 217,080.00) |
| Waterfall step 10: Gross amount differences | 900.00 (running 217,980.00) |
| Waterfall step 11: Rounding | -0.03 (running 217,979.97) |
| Waterfall total bar | 217,979.97 (= gateway SETTLED total 217,979.97) |
| Bar, BREAK: duplicate internal SUCCESS deposit for one settlement (double-credit risk) | 6 |
| Bar, BREAK: deposit SUCCESS, no gateway settlement found | 5 |
| Bar, BREAK: settled fee differs from contracted fee | 4 |
| Bar, BREAK: settled gross amount differs from internal amount | 4 |
| Bar, BREAK: duplicate gateway settlement for one reference (double-credit risk) | 4 |
| Bar, BREAK: unrecognised settlement (no internal record) | 4 |
| Bar, NOT A PROBLEM: rounding difference <= 1 cent | 3 |
| Bar, REVERSAL: gateway reversed/charged back after settlement | 3 |
| Bar, TIMING: settlement expected in next period (created near cut-off) | 3 |
| Bar, TIMING: prior-period deposit settled at start of period | 3 |
| Bar, BREAK: net amount is not gross minus fee | 2 |
| Bar, BREAK: payment confirmed, wallet not credited | 2 |

## Page 4: Ingestion monitoring

| Visual | Expected |
|---|---|
| Card: Transactions Loaded | 1,024 |
| Card: Ingestion Runs | 3 |
| Card: Rows Rejected | 1 |
| Card: Rate-Limit Retries | 1 |
| Column, completed | 587 |
| Column, failed | 214 |
| Column, pending | 207 |
| Column, reversed | 16 |
