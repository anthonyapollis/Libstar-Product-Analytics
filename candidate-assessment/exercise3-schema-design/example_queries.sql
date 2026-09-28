-- Exercise 3: the four required example queries, run against the seed data.
-- Assumption (stated per the brief's "write it down and continue" instruction):
--   GGR = stakes - payouts (before bonus cost and tax), consistent with the
--   standard industry definition. NGR = GGR - bonus cost. No regulatory levy is
--   modelled here (not specified in the brief); a real deployment would add a
--   tax/levy line once the jurisdiction is confirmed, exactly as the finance
--   ebook's KPI catalogue flags NGR as "once definition is agreed".
USE jsb_platform;

-- ---------------------------------------------------------------------------
-- (a) NGR by product for a month
-- ---------------------------------------------------------------------------
WITH product_ggr AS (
    SELECT product,
           SUM(stake_real_amount + stake_bonus_amount) AS turnover,
           SUM(payout_amount) AS payouts,
           SUM(stake_real_amount + stake_bonus_amount) - SUM(payout_amount) AS ggr
    FROM bets
    WHERE settled_at_utc >= '2026-09-01' AND settled_at_utc < '2026-10-01'
      AND status IN ('won','lost')          -- exclude still-open bets from a revenue view
    GROUP BY product
),
product_bonus_cost AS (
    -- Bonus cost realised this month, allocated to product via the bet it was staked on
    -- (only the portion of a bonus that was actually wagered and lost is a realised cost;
    -- bonus still in play is a liability, not yet a cost -- see design_notes.md).
    SELECT b.product, SUM(wt.amount) AS bonus_cost
    FROM wallet_transactions wt
    JOIN bets b ON b.bet_id = wt.related_bet_id
    WHERE wt.txn_type = 'bet_stake' AND wt.balance_type = 'bonus'
      AND b.status = 'lost'
      AND b.settled_at_utc >= '2026-09-01' AND b.settled_at_utc < '2026-10-01'
    GROUP BY b.product
)
SELECT g.product, g.turnover, g.payouts, g.ggr,
       COALESCE(c.bonus_cost, 0) AS bonus_cost,
       g.ggr - COALESCE(c.bonus_cost, 0) AS ngr
FROM product_ggr g
LEFT JOIN product_bonus_cost c ON c.product = g.product
ORDER BY g.product;

-- ---------------------------------------------------------------------------
-- (b) bonus cost as a % of NGR, by campaign
-- ---------------------------------------------------------------------------
WITH campaign_cost AS (
    -- Recognise cost when a grant resolves (spent via loss, expired or forfeited);
    -- an 'active' grant is a liability (see bonus_liability in the KPI catalogue),
    -- not a cost yet.
    SELECT pb.campaign_id, SUM(pb.granted_amount) AS bonus_cost
    FROM player_bonuses pb
    WHERE pb.status IN ('completed','expired','forfeited')
      AND pb.resolved_at_utc >= '2026-09-01' AND pb.resolved_at_utc < '2026-10-01'
    GROUP BY pb.campaign_id
),
-- Company-wide NGR for the period: GGR minus ALL realised bonus cost (every
-- product, every campaign) -- not just the campaign being measured in this
-- query. Must use the same GGR-minus-bonus-cost definition as query (a),
-- not just raw turnover-minus-payouts, or the % is measured against the
-- wrong base.
period_ggr AS (
    SELECT SUM(stake_real_amount + stake_bonus_amount) - SUM(payout_amount) AS total_ggr
    FROM bets
    WHERE settled_at_utc >= '2026-09-01' AND settled_at_utc < '2026-10-01'
      AND status IN ('won','lost')
),
period_bonus_cost AS (
    SELECT SUM(wt.amount) AS total_bonus_cost
    FROM wallet_transactions wt
    JOIN bets b ON b.bet_id = wt.related_bet_id
    WHERE wt.txn_type = 'bet_stake' AND wt.balance_type = 'bonus'
      AND b.status = 'lost'
      AND b.settled_at_utc >= '2026-09-01' AND b.settled_at_utc < '2026-10-01'
),
period_ngr AS (
    SELECT (SELECT total_ggr FROM period_ggr)
           - COALESCE((SELECT total_bonus_cost FROM period_bonus_cost), 0) AS total_ngr
)
SELECT bc.name AS campaign, cc.bonus_cost,
       ROUND(100 * cc.bonus_cost / NULLIF((SELECT total_ngr FROM period_ngr), 0), 2) AS bonus_cost_pct_of_ngr
FROM campaign_cost cc
JOIN bonus_campaigns bc ON bc.campaign_id = cc.campaign_id;

-- ---------------------------------------------------------------------------
-- (c) a player's balance at a given date and time
--     (proves the ledger is authoritative: balance is a SUM, not a lookup)
-- ---------------------------------------------------------------------------
SET @player_id = 1;
SET @as_of = '2026-09-06 00:00:00';

SELECT
    balance_type,
    SUM(CASE WHEN direction = 'credit' THEN amount ELSE -amount END) AS balance_as_of
FROM wallet_transactions
WHERE player_id = @player_id
  AND created_at_utc <= @as_of
  AND status = 'posted'
GROUP BY balance_type;

-- Cross-check against the live cache (only valid when @as_of = now):
-- SELECT real_balance, bonus_balance FROM wallets WHERE player_id = @player_id;

-- ---------------------------------------------------------------------------
-- (d) deposits that failed and the player later succeeded
-- ---------------------------------------------------------------------------
SELECT f.player_id, f.deposit_attempt_id AS failed_attempt_id, f.created_at_utc AS failed_at,
       s.deposit_attempt_id AS succeeded_attempt_id, s.created_at_utc AS succeeded_at,
       TIMESTAMPDIFF(MINUTE, f.created_at_utc, s.created_at_utc) AS minutes_to_success,
       s.amount AS succeeded_amount
FROM deposit_attempts f
JOIN deposit_attempts s
  ON s.player_id = f.player_id
 AND s.status = 'success'
 AND s.created_at_utc > f.created_at_utc
 AND s.created_at_utc <= f.created_at_utc + INTERVAL 24 HOUR   -- "later" bounded to same session/day
WHERE f.status = 'failed'
-- keep only the first success after each failure
AND NOT EXISTS (
    SELECT 1 FROM deposit_attempts s2
    WHERE s2.player_id = f.player_id AND s2.status = 'success'
      AND s2.created_at_utc > f.created_at_utc AND s2.created_at_utc < s.created_at_utc
)
ORDER BY f.created_at_utc;
