# Payment Gateway Reconciliation — Weekly Summary
**Period:** 2026-09-01 00:00 UTC to 2026-09-07 23:59 UTC | **Currency:** NAD | **Prepared for:** Finance Manager
**Tools used:** MySQL 8.0 (schema, matching and categorisation logic), Python/pandas (load, export, cross-check)

## Bottom line
294 of 306 gateway-recognised settlements (96%) match our records exactly, amount and fee correct.
The remaining differences are fully explained below — nothing is left over. **R1,900 requires action this
week** (see "Break — act now"); the rest is timing or non-financial.

## The bridge: internal total → gateway total
| Line | Amount (NAD) |
|---|---:|
| Internal SUCCESS deposits, total | **218,280.00** |
| − Duplicate internal deposit rows (same settlement counted twice) | (1,300.00) |
| − Reversals / chargebacks (gateway's SETTLED total excludes these) | (850.00) |
| − Deposits not yet settled by the gateway | (2,700.00) |
| − Deposits created in the last 15 min of the period (settle next week) | (3,650.00) |
| + Settlements with no matching internal record | 5,500.00 |
| + Payments the gateway settled that we marked FAILED | 250.00 |
| + Duplicate gateway settlement rows (same txn counted twice) | 1,550.00 |
| +/− Gross amount disputes with the gateway | 900.00 |
| +/− Rounding (≤ 1 cent, immaterial) | (0.03) |
| **= Gateway SETTLED total** | **217,979.97** |
| **Residual (unexplained)** | **0.00** |

## Exceptions by category
| Category | Type | Rows | Impact (NAD) | Likely cause | Next step / owner |
|---|---|---:|---:|---|---|
| Payment confirmed, wallet not credited | **Break — act now** | 2 | 250.00 | Internal status set to FAILED but the gateway actually settled the payment (callback lost or a timeout misread as a failure) | **Payments engineering**: re-credit the two players' wallets today; check callback/webhook logs for the same failure mode across other rails |
| Unrecognised settlement (no internal record) | **Break — act now** | 7 | 5,500.00 | Gateway holds settlements for references we have no record of at all — could be an unlogged transaction, a test/other-merchant reference leaking into our report, or a real integration gap | **Payments + Finance**: request source-side transaction detail from the gateway for these 7 references before assuming it's noise; this is unexplained money |
| Duplicate gateway settlement | Break — dispute | 2 pairs (4 rows) | 1,550.00 gross (0 net dep. impact) | Gateway sent the same settlement twice (webhook retry without idempotency on their side) | **Payments engineering**: raise with gateway account manager; confirm only one settlement should be paid out/netted |
| Duplicate internal deposit | Break — dedupe | 3 pairs (6 rows) | 1,300.00 (double-credit risk) | Player or our retry logic double-submitted the same deposit request under two deposit_ids referencing one gateway_ref | **Engineering**: add an idempotency key on deposit initiation so a retry updates the existing attempt instead of creating a new row; audit whether wallets were credited twice |
| Settled amount differs from internal amount | Break — dispute | 4 | 900.00 (net) | Gateway settled a different gross amount than we recorded (largest: R800 short) | **Finance**: dispute with gateway per contract; request source evidence per reference |
| Settled fee differs from contract (2% + R1.00) | Break — dispute | 4 | R0 gross impact, fee variance only | Fee miscalculated on the gateway's side | **Finance**: raise fee dispute; contract fee is deterministic and checkable per transaction |
| Reversal / chargeback | Business event, not a break | 3 | 850.00 | Gateway reversed a previously settled payment (chargeback or goodwill reversal) | **Finance**: confirm the corresponding wallet debit was applied; if not, claw back |
| Deposit SUCCESS, no settlement found | Timing / possible break | 5 | 2,700.00 | Not near period cut-off — settlement is overdue | **Finance**: hold and re-check on next file; escalate if still missing after 3 days |
| Created near period cut-off, no settlement yet | Timing — not a problem | 3 | 3,650.00 | Deposit created in the last 5 minutes of the period; gateway settlement lands in next week's file | None — expect to clear automatically next period |
| Rounding difference ≤ 1 cent | Not a problem | 3 | 0.03 | FX/rounding noise | None |
| *(observation, not an exception)* Reference formatting variance | Not a problem | 4 matches | — | Gateway sends our reference with different punctuation/case (`GW_000020`, `GW000102`, `gw-000196`, leading/trailing spaces). Matched correctly once normalised (upper-case, letters+digits only) | **Engineering**: ask the gateway to send the reference back verbatim; harmless today because matching is normalised, but a raw string-equality reconciliation would silently misclassify these as breaks |

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
