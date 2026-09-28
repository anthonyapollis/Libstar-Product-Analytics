# Payment Gateway Reconciliation — Weekly Summary
**Period:** 2026-09-01 00:00 UTC to 2026-09-07 23:59 UTC | **Currency:** NAD | **Prepared for:** Finance Manager
**Tools used:** MySQL 8.0 (schema, matching and categorisation logic), Python/pandas (load, export, cross-check)

## Finance Manager summary (one page)
A one-page version of this section, with the bridge, is `Finance_Summary.pdf`.

**274 of the 306 gateway settlements (90%) match exactly** on reference, gross, fee and net. The
bridge from our R218,280.00 to the gateway's R217,979.97 leaves **R0.00 unexplained**. Two of its
timing lines are provisional until the adjacent weeks' files confirm them (see assumptions).

### Bridge on gross amounts: internal total → gateway total
| Line | NAD |
|---|---:|
| Internal SUCCESS deposits, total | **218,280.00** |
| − Duplicate internal deposit rows (same settlement counted twice) | (1,300.00) |
| − Reversals / chargebacks (not in the gateway's SETTLED total) | (850.00) |
| − Deposits with no settlement yet (mid-week) | (2,700.00) |
| − Created in the last 15 min, not yet settled (**provisional**) | (3,650.00) |
| + Settled in the first 15 min, no deposit this week (**provisional**) | 2,600.00 |
| + Settlements with no internal record | 2,900.00 |
| + Settled by the gateway but marked FAILED by us | 250.00 |
| + Duplicate gateway settlement rows | 1,550.00 |
| +/− Gross amount differences with the gateway (net) | 900.00 |
| +/− Rounding (exactly 1 cent on 3 rows) | (0.03) |
| **= Gateway SETTLED total** | **217,979.97** |
| **Residual (unexplained)** | **0.00** |

### Priority actions
| When | Action | Owner | NAD |
|---|---|---|---:|
| Today | Re-credit 2 players: marked FAILED by us, settled by the gateway | Payments | 250.00 |
| Today | Get gateway detail for 4 unrecognised settlements (GW-000301 to 304) | Payments | 2,900.00 |
| This week | Dispute 4 gross differences (3 players under-credited R950, 1 over-credited R50) | Finance | 900.00 net |
| This week | Claim fee overcharges (4) and short-paid nets (2) | Finance | 7.75 |
| This week | Did 2 duplicate settlements pay twice? Audit 3 duplicate deposits for double credits | Payments | 1,550 / 1,300 |
| This week | Confirm the wallet debit for each of 3 reversals | Finance | 850.00 |
| 3 days | 5 deposits with no settlement: re-check the next file, then escalate | Finance | 2,700.00 |

### Material assumptions
- **The timing lines are provisional.** This week's files can't prove them.
  - R3,650 (3 deposits created 23:54–23:55 on 7 Sep) should appear in the 8–14 Sep gateway file.
  - R2,600 (3 settlements at 00:04–00:06 on 1 Sep, GW-000331 to 333) should match deposits in the
    25–31 Aug internal file.

  Finance keeps all six open until they are matched. Any item still unmatched after those files
  becomes a break (missing or unrecognised settlement).
- **Fee rule.** Fee = 2% of gross + R1.00, to the cent. Any fee or net difference of 1 cent or more
  is flagged. Gross differences of exactly 1 cent (3 rows, R0.03) are treated as rounding. That is a
  materiality choice for Finance to confirm. Boundary tests at 1, 2 and 3 cents are in
  `sql/06_threshold_fixtures.py`.
- **Fee and net errors aren't bridge lines.** The bridge is on gross, which is what our deposits
  record. Fee and net errors don't move gross, so they appear as actions instead.

## Supporting detail

### Exceptions by category
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
| Created in the last 15 min, no settlement yet | Timing — provisional | 3 | 3,650.00 | Created at 23:54–23:55 on the last day. The settlement is expected in next week's file, but this week's data can't prove it | **Finance**: match against the 8–14 Sep gateway file; any still missing becomes a break |
| Settled in the first 15 min, no internal record | Timing — provisional | 3 | 2,600.00 | Settled at 00:04–00:06 on the first day, with references that appear nowhere in this week's deposits. Likely deposits created just before midnight last week, but this week's data can't prove it | **Finance**: match against the 25–31 Aug internal file (GW-000331 to 333); any unmatched becomes an unrecognised settlement |
| Rounding difference of exactly 1 cent | Not a problem (materiality choice) | 3 | 0.03 | Rounding noise | **Finance**: confirm 1 cent is immaterial |
| *(observation, not an exception)* Reference formatting variance | Not a problem | 6 | — | The gateway returns our reference with different punctuation, case or spacing (`GW_000020`, `GW000102`, `gw-000196 `, `gw-000227`, ` GW-000267 `, `gw-000284`). These match once normalised to upper-case letters and digits | **Engineering**: ask the gateway to return references verbatim. An exact-match reconciliation would misclassify these as breaks. A case-insensitive database collation hides three of them, which is how an earlier count of 4 undercounted |

Full row-level detail, one line per exception with its category and explanation, is in `exceptions.csv`.

### Automating this daily
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
