-- Exercise 1: Payment gateway reconciliation logic
-- Tool: MySQL 8.0
--
-- Contract: fee = ROUND(gross_amount * 0.02 + 1.00, 2); net_amount = gross_amount - fee.
-- Matching key: normalised gateway_ref / merchant_ref (letters+digits, upper-cased) because the
-- gateway file sends the same reference with different punctuation/case/whitespace.
-- Period: 2026-09-01 00:00:00 to 2026-09-07 23:59:59 UTC.

USE jsb_assessment;

-- ---------------------------------------------------------------------------
-- 0. Control totals (first thing any daily job should log, before anything else)
-- ---------------------------------------------------------------------------
SELECT 'internal_deposits' AS source, COUNT(*) AS row_count,
       SUM(CASE WHEN status='SUCCESS' THEN amount ELSE 0 END) AS success_amount_total
FROM internal_deposits
UNION ALL
SELECT 'gateway_settlement', COUNT(*),
       SUM(CASE WHEN status='SETTLED' THEN gross_amount ELSE 0 END)
FROM gateway_settlement;

-- ---------------------------------------------------------------------------
-- 1. Flag reference-level duplicates on each side up front (affects matching)
-- ---------------------------------------------------------------------------
-- Plain (non-TEMPORARY) helper tables: MySQL cannot reopen the same TEMPORARY
-- table twice in one statement, and gw_dupe_flag below is joined twice
-- (once per branch of the UNION ALL that builds `matched`).
DROP TABLE IF EXISTS dep_dupe_flag;
CREATE TABLE dep_dupe_flag AS
SELECT deposit_id, gateway_ref_norm,
       COUNT(*) OVER (PARTITION BY gateway_ref_norm) AS dep_ref_count
FROM internal_deposits
WHERE status = 'SUCCESS';

DROP TABLE IF EXISTS gw_dupe_flag;
CREATE TABLE gw_dupe_flag AS
SELECT row_id, merchant_ref_norm,
       COUNT(*) OVER (PARTITION BY merchant_ref_norm) AS gw_ref_count
FROM gateway_settlement;

-- ---------------------------------------------------------------------------
-- 2. Full outer join (emulated: MySQL has no FULL OUTER JOIN) between
--    SUCCESS deposits and settlement rows, on the normalised reference.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS matched;
CREATE TABLE matched AS
SELECT d.deposit_id, d.player_id, d.created_at, d.amount AS dep_amount,
       d.gateway_ref, d.status AS dep_status,
       g.row_id AS gw_row_id, g.gateway_txn_id, g.merchant_ref, g.settled_at,
       g.gross_amount, g.fee, g.net_amount, g.status AS gw_status,
       ddf.dep_ref_count, gdf.gw_ref_count
FROM internal_deposits d
LEFT JOIN gateway_settlement g ON g.merchant_ref_norm = d.gateway_ref_norm
LEFT JOIN dep_dupe_flag ddf ON ddf.deposit_id = d.deposit_id
LEFT JOIN gw_dupe_flag gdf ON gdf.row_id = g.row_id
WHERE d.status = 'SUCCESS'

UNION ALL

-- Gateway rows not matched to any SUCCESS deposit above: either they belong to
-- a FAILED deposit (money settled but wallet never credited), or there is no
-- internal record for the reference at all. LEFT JOIN internal_deposits on ANY
-- status (not just SUCCESS) so we can tell the two apart.
SELECT d2.deposit_id, d2.player_id, d2.created_at, d2.amount, g.merchant_ref, d2.status,
       g.row_id, g.gateway_txn_id, g.merchant_ref, g.settled_at,
       g.gross_amount, g.fee, g.net_amount, g.status,
       NULL, gdf.gw_ref_count
FROM gateway_settlement g
LEFT JOIN gw_dupe_flag gdf ON gdf.row_id = g.row_id
LEFT JOIN internal_deposits d2 ON d2.gateway_ref_norm = g.merchant_ref_norm
WHERE NOT EXISTS (
    SELECT 1 FROM internal_deposits d
    WHERE d.gateway_ref_norm = g.merchant_ref_norm AND d.status = 'SUCCESS'
);

-- ---------------------------------------------------------------------------
-- 3. Categorise every row. This is the exception list.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS recon_exceptions;
CREATE TABLE recon_exceptions AS
SELECT
    m.deposit_id, m.player_id, m.created_at, m.dep_amount,
    m.gateway_ref, m.gateway_txn_id, m.merchant_ref, m.settled_at,
    m.gross_amount, m.fee, m.net_amount, m.gw_status,
    ROUND(m.gross_amount * 0.02 + 1.00, 2) AS expected_fee,
    CASE
        -- Genuine break: money settled by the gateway, but our own record says the
        -- deposit failed -> the platform never credited the player's wallet.
        WHEN m.dep_status = 'FAILED' AND m.gw_status = 'SETTLED'
            THEN 'BREAK: payment confirmed, wallet not credited'

        -- Genuine break: gateway settlement references a merchant_ref we have no
        -- record of at all (not even a FAILED attempt).
        WHEN m.deposit_id IS NULL AND m.gw_status = 'SETTLED'
            THEN 'BREAK: unrecognised settlement (no internal record)'

        -- Genuine break: we have >1 SUCCESS deposit row pointing at one settlement.
        WHEN m.dep_ref_count > 1
            THEN 'BREAK: duplicate internal SUCCESS deposit for one settlement (double-credit risk)'

        -- Genuine break: the gateway sent >1 settlement row for the same reference.
        WHEN m.gw_ref_count > 1
            THEN 'BREAK: duplicate gateway settlement for one reference (double-credit risk)'

        -- Timing, not a problem: deposit created very close to period end, gateway
        -- settlement simply has not landed in this extract yet.
        WHEN m.gw_row_id IS NULL AND m.created_at >= '2026-09-07 23:45:00'
            THEN 'TIMING: settlement expected in next period (created near cut-off)'

        -- Genuine break: SUCCESS deposit with no settlement anywhere, not a cut-off case.
        WHEN m.gw_row_id IS NULL
            THEN 'BREAK: deposit SUCCESS, no gateway settlement found'

        -- Business event, not an arithmetic break, but needs a wallet clawback.
        WHEN m.gw_status = 'REVERSED'
            THEN 'REVERSAL: gateway reversed/charged back after settlement'

        -- Fee doesn't match the 2% + R1 contract -> dispute-worthy.
        WHEN ABS(m.fee - ROUND(m.gross_amount * 0.02 + 1.00, 2)) > 0.02
            THEN 'BREAK: settled fee differs from contracted fee'

        -- Gross amount differs from what we recorded, beyond rounding noise.
        WHEN ABS(m.dep_amount - m.gross_amount) > 0.02
            THEN 'BREAK: settled gross amount differs from internal amount'

        -- Within 1 cent: FX/rounding noise, not worth investigating.
        WHEN ABS(m.dep_amount - m.gross_amount) BETWEEN 0.005 AND 0.02
            THEN 'NOT A PROBLEM: rounding difference <= 1 cent'

        ELSE 'OK: matched, amount and fee correct'
    END AS category,
    CASE
        WHEN m.dep_status = 'FAILED' AND m.gw_status = 'SETTLED' THEN m.gross_amount
        WHEN m.deposit_id IS NULL AND m.gw_status = 'SETTLED' THEN m.gross_amount
        WHEN m.gw_row_id IS NULL THEN m.dep_amount
        WHEN m.gw_status = 'REVERSED' THEN m.gross_amount
        ELSE ROUND(COALESCE(m.dep_amount,0) - COALESCE(m.gross_amount,0), 2)
    END AS financial_impact
FROM matched m;

-- Helper tables no longer needed once recon_exceptions is built.
DROP TABLE IF EXISTS dep_dupe_flag;
DROP TABLE IF EXISTS gw_dupe_flag;
DROP TABLE IF EXISTS matched;

-- Only exceptions (drop the clean matches) for the deliverable CSV.
SELECT * FROM recon_exceptions WHERE category NOT LIKE 'OK:%' ORDER BY category, created_at;

-- ---------------------------------------------------------------------------
-- 4. Summary counts by category, for the one-page report
-- ---------------------------------------------------------------------------
SELECT category, COUNT(*) AS n, ROUND(SUM(financial_impact),2) AS impact_total
FROM recon_exceptions
GROUP BY category
ORDER BY n DESC;

-- ---------------------------------------------------------------------------
-- 5. The bridge: internal SUCCESS total -> gateway SETTLED total
-- ---------------------------------------------------------------------------
SELECT
  (SELECT ROUND(SUM(amount),2) FROM internal_deposits WHERE status='SUCCESS')                AS internal_success_total,
  (SELECT ROUND(SUM(gross_amount),2) FROM gateway_settlement WHERE status='SETTLED')          AS gateway_settled_total,
  (SELECT ROUND(SUM(financial_impact),2) FROM recon_exceptions
     WHERE category = 'BREAK: payment confirmed, wallet not credited')                        AS plus_unrecorded_settlements_failed_flag,
  (SELECT ROUND(SUM(financial_impact),2) FROM recon_exceptions
     WHERE category = 'BREAK: unrecognised settlement (no internal record)')                  AS plus_unrecognised_settlements,
  (SELECT ROUND(SUM(financial_impact),2) FROM recon_exceptions
     WHERE category LIKE 'BREAK: duplicate%settlement%')                                      AS plus_duplicate_settlements,
  (SELECT ROUND(SUM(financial_impact),2) FROM recon_exceptions
     WHERE category = 'REVERSAL: gateway reversed/charged back after settlement')             AS less_reversals,
  (SELECT ROUND(SUM(financial_impact),2) FROM recon_exceptions
     WHERE category = 'BREAK: deposit SUCCESS, no gateway settlement found')                  AS less_missing_settlements,
  (SELECT ROUND(SUM(financial_impact),2) FROM recon_exceptions
     WHERE category = 'TIMING: settlement expected in next period (created near cut-off)')    AS less_timing_not_yet_settled;
