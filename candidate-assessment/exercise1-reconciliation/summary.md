# Payment Gateway Reconciliation — Weekly Summary
**Period:** 2026-09-01 00:00 UTC to 2026-09-07 23:59 UTC | **Currency:** NAD | **Prepared for:** Finance Manager
**Tools used:** MySQL 8.0 (schema, matching and categorisation logic), Python/pandas (load, export, cross-check)

## Bottom line
**274 of the 306 settlement rows (90%) match exactly** on reference, amount, fee and net. Three more
differ by under a cent. The other 29 are categorised below, and the bridge from our total to the
gateway's total reconciles with **R0.00 unexplained**.

- **Act this week: R3,150.** R250 is owed to two players whose deposits we marked FAILED although the
  gateway settled them. R2,900 is settlements for four references we have no record of.
- **The gateway owes us R7.75:** R3.75 in fees above the contract rate, and R4.00 short-paid on two
  settlements where net ≠ gross − fee.
- **R950 of gross-amount differences** suggest three players were under-credited. A fourth (R50) runs
  the other way. Dispute all four with the gateway.
- **Timing, not problems:** R3,650 of deposits from the last minutes of the week settle next week.
  R2,600 settled in this week's first six minutes and almost certainly belongs to last week's deposits.

## The bridge: internal total → gateway total
| Line | Amount (NAD) |
|---|---:|
| Internal SUCCESS deposits, total | **218,280.00** |
| − Duplicate internal deposit rows (same settlement counted twice) | (1,300.00) |
| − Reversals / chargebacks (gateway's SETTLED total excludes these) | (850.00) |
| − Deposits not yet settled by the gateway | (2,700.00) |
| − Deposits created in the last 15 min of the period (settle next week) | (3,650.00) |
| + Settled in the first 15 min of the period (last week's deposits) | 2,600.00 |
| + Settlements with no matching internal record | 2,900.00 |
| + Payments the gateway settled that we marked FAILED | 250.00 |
| + Duplicate gateway settlement rows (same txn counted twice) | 1,550.00 |
| +/− Gross amount differences with the gateway (net) | 900.00 |
| +/− Rounding (≤ 1 cent, immaterial) | (0.03) |
| **= Gateway SETTLED total** | **217,979.97** |
| **Residual (unexplained)** | **0.00** |

The bridge is on gross amounts, because that's what our deposits record. Fee and net-amount errors
don't move gross, so they sit outside it and are listed as their own exceptions.

## Exceptions by category
| Category | Type | Rows | Impact (NAD) | Likely cause | Next step / owner |
|---|---|---:|---:|---|---|
| Payment confirmed, wallet not credited | **Break — act now** | 2 | 250.00 | Internal status set to FAILED but the gateway actually settled the payment (callback lost or a timeout misread as a failure) | **Payments engineering**: re-credit the two players' wallets today; check callback/webhook logs for the same failure mode across other rails |
| Unrecognised settlement (no internal record) | **Break — act now** | 4 | 2,900.00 | Settled mid-week for references that appear nowhere in our records, not even as failed attempts. Could be an unlogged transaction, another merchant's reference, or an integration gap | **Payments + Finance**: request the gateway's transaction detail for GW-000301 to GW-000304 before treating any of it as ours |
| Net amount is not gross minus fee | Break — dispute | 2 | 4.00 short-paid | The gateway's own arithmetic is wrong: GT900133 and GT900289 each paid R2 less than gross − fee | **Finance**: claim the R4.00; ask the gateway how net is calculated |
| Settled fee differs from contract (2% + R1.00) | Break — dispute | 4 | 3.75 overcharged | Fee above contract on four settlements (R0.50 to R1.50 each) | **Finance**: raise a fee dispute. The contract fee is deterministic, so every settlement can be checked automatically |
| Settled amount differs from internal amount | Break — dispute | 4 | 900.00 (net) | Gateway settled a different gross amount from the one we recorded. Three are higher than ours (R100, R800, R50: players under-credited); one is R50 lower (we over-credited) | **Finance**: dispute each with source evidence; correct the player wallets once agreed |
| Duplicate gateway settlement | Break — dispute | 2 pairs (4 rows) | 1,550.00 gross | Gateway reported the same transaction twice, at different times (webhook retry without idempotency on their side) | **Payments engineering**: confirm with the gateway whether money moved twice or only the report duplicated |
| Duplicate internal deposit | Break — dedupe | 3 pairs (6 rows) | 1,300.00 (double-credit risk) | The same deposit was submitted twice, 40 seconds apart, creating two deposit_ids for one gateway_ref | **Engineering**: add an idempotency key on deposit initiation; audit whether these wallets were credited twice |
| Reversal / chargeback | Business event, not a break | 3 | 850.00 | Gateway reversed a previously settled payment (chargeback or goodwill reversal) | **Finance**: confirm the matching wallet debit was applied; if not, claw back |
| Deposit SUCCESS, no settlement found | Timing / possible break | 5 | 2,700.00 | Mid-week deposits with no settlement at all, well beyond the normal lag (median 28 min, longest 5 h 45 min) | **Finance**: re-check on the next file; escalate if still missing after 3 days |
| Created in the last 15 min, no settlement yet | Timing — not a problem | 3 | 3,650.00 | Created at 23:54–23:55 on the last day; the settlement lands in next week's file | None; expect it to clear next period |
| Settled in the first 15 min, no internal record | Timing — not a problem | 3 | 2,600.00 | Settled at 00:04–00:06 on the first day, with references that appear nowhere in this week's deposits. The deposits were almost certainly created just before midnight last week | **Finance**: confirm against last week's internal file (GW-000331 to 333) |
| Rounding difference ≤ 1 cent | Not a problem | 3 | 0.03 | Rounding noise | None |
| *(observation, not an exception)* Reference formatting variance | Not a problem | 6 | — | The gateway returns our reference with different punctuation, case or spacing (`GW_000020`, `GW000102`, `gw-000196 `, `gw-000227`, ` GW-000267 `, `gw-000284`). These match once normalised to upper-case letters and digits | **Engineering**: ask the gateway to return references verbatim. An exact-match reconciliation would misclassify these as breaks. A case-insensitive database collation hides three of them, which is how an earlier count of 4 undercounted |

Full row-level detail, one line per exception with its category and explanation, is in `exceptions.csv`.

## Automating this daily
This is no longer just a proposal: the same categorisation logic lives as a dbt model
(`../dbt_jsb_assessment/models/marts/fct_recon_exceptions.sql`), schedulable via `dbt build` today, with
two tests that fail the run if anything's wrong — `assert_recon_bridge_reconciles` (the R0.00 residual
below, enforced in SQL, not just checked once by hand) and `assert_recon_covers_all_sources` (no source
row silently dropped). The steps below are what a daily schedule around it looks like:
1. **Ingest** both feeds daily (API/SFTP pull) into raw landing tables, keyed by their natural identifiers — never overwrite, land as-is.
2. **Match** using the normalised-reference join (`stg_internal_deposits` / `stg_gateway_settlement` → `fct_recon_exceptions`), re-run as a scheduled job (dbt + Airflow/cron) after both feeds have landed for the day.
3. **Control totals first**: log source row count and sum before matching (see query 0). A count/sum mismatch against what the source declares is itself an alert, independent of row-level matching.
4. **Persist `recon_exceptions` daily** (don't overwrite history) so ageing and trend reporting is possible, and so a corrected file never silently rewrites what was reported yesterday.
5. **Alerts** (Slack/email/PagerDuty depending on severity):
   - **Critical, page immediately**: any "payment confirmed, wallet not credited" or "unrecognised settlement" — real money at risk.
   - **High, same-day**: new duplicate settlement/deposit rows; gross-amount or fee disputes above a materiality threshold (e.g. > R50).
   - **Daily digest only**: reversals, timing items still within the cut-off window, rounding noise.
   - **Threshold alert**: match rate drops below e.g. 95%, or unreconciled value exceeds e.g. R5,000 — signals a systemic issue, not just one-off breaks.
6. **Ageing**: exceptions unresolved after 3 days escalate automatically to Finance management; unresolved after 7 days require a signed-off write-off or gateway credit note.
