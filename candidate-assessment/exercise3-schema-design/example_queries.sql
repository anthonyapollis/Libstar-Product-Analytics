-- Exercise 3: the four required queries, run against the seed data.
--
-- Definitions (assumptions, written down per the brief):
--   * GGR = stakes - payouts on bets settled in the period (won or lost; void and open bets excluded).
--     Stakes include the bonus-funded part, as the product sees them.
--   * Bonus cost = the bonus money wagered on those settled bets (bets.stake_bonus_amount). Bonus money
--     is not revenue, so it is taken back out: NGR = GGR - bonus cost (which equals real-money stakes -
--     payouts). A win on a bonus-funded bet is already in payouts, so converting bonus winnings to real
--     money later is not counted twice. An unwagered bonus that expires or is forfeited costs nothing;
--     one still active is a liability, not yet a cost.
--   * The same definition is used for (a) and (b), in the dbt marts, in Power BI and on Databricks.
--   * No betting levy or tax line: the brief doesn't give one. It would be one more deduction in (a).
--   * Periods are calendar months in UTC, cut on settled_at_utc.
USE jsb_platform;

-- ---------------------------------------------------------------------------
-- (a) NGR by product for a month
-- ---------------------------------------------------------------------------
SET @month_start = '2026-09-01', @month_end = '2026-10-01';

SELECT product,
       SUM(stake_real_amount + stake_bonus_amount)                        AS turnover,
       SUM(payout_amount)                                                 AS payouts,
       SUM(stake_real_amount + stake_bonus_amount) - SUM(payout_amount)   AS ggr,
       SUM(stake_bonus_amount)                                            AS bonus_cost,
       SUM(stake_real_amount + stake_bonus_amount) - SUM(payout_amount)
         - SUM(stake_bonus_amount)                                        AS ngr
FROM bets
WHERE status IN ('won', 'lost')
  AND settled_at_utc >= @month_start AND settled_at_utc < @month_end   -- ix_bets_product_settled
GROUP BY product
ORDER BY product;

-- ---------------------------------------------------------------------------
-- (b) Bonus cost as a % of NGR, by campaign
--     A bet's bonus-funded stake is traced to the grant that paid it (bets.player_bonus_id), and the
--     grant to its campaign. The denominator is the whole month's NGR from (a), all products.
-- ---------------------------------------------------------------------------
WITH settled AS (
    SELECT * FROM bets
    WHERE status IN ('won', 'lost')
      AND settled_at_utc >= @month_start AND settled_at_utc < @month_end
),
campaign_cost AS (
    SELECT pb.campaign_id, SUM(s.stake_bonus_amount) AS bonus_cost
    FROM settled s
    JOIN player_bonuses pb ON pb.player_bonus_id = s.player_bonus_id
    GROUP BY pb.campaign_id
),
period_ngr AS (
    SELECT SUM(stake_real_amount + stake_bonus_amount) - SUM(payout_amount) - SUM(stake_bonus_amount) AS total_ngr
    FROM settled
)
SELECT c.name AS campaign, cc.bonus_cost, n.total_ngr,
       ROUND(100 * cc.bonus_cost / NULLIF(n.total_ngr, 0), 2) AS bonus_cost_pct_of_ngr
FROM campaign_cost cc
JOIN bonus_campaigns c ON c.campaign_id = cc.campaign_id
CROSS JOIN period_ngr n
ORDER BY c.name;

-- ---------------------------------------------------------------------------
-- (c) A player's balance at a given date and time
--     The sum of the ledger up to that moment. Every row counts, reversals included: a reversal is
--     its own opposite row, so the original and its reversal cancel out. Nothing is filtered away.
-- ---------------------------------------------------------------------------
SET @player_id = 1, @as_of = '2026-09-06 00:00:00';

SELECT balance_type,
       SUM(CASE WHEN direction = 'credit' THEN amount ELSE -amount END) AS balance_as_of
FROM wallet_transactions
WHERE player_id = @player_id
  AND created_at_utc <= @as_of                                         -- ix_wtxn_player_time
GROUP BY balance_type
ORDER BY balance_type;

-- The same query for player 2 either side of the correction in seed.sql: 450.00 while the wrong
-- 50.00 credit stood, 415.00 once it was reversed and the right 15.00 posted.
SELECT t.as_of, w.balance_type,
       SUM(CASE WHEN w.direction = 'credit' THEN w.amount ELSE -w.amount END) AS balance_as_of
FROM (SELECT CAST('2026-09-12 09:15:00' AS DATETIME(6)) AS as_of
      UNION ALL SELECT CAST('2026-09-12 10:00:00' AS DATETIME(6))) t
JOIN wallet_transactions w ON w.player_id = 2 AND w.created_at_utc <= t.as_of
WHERE w.balance_type = 'real'
GROUP BY t.as_of, w.balance_type
ORDER BY t.as_of;

-- The ledger's own check: each row's balance_after must follow from the row before it in the same
-- wallet and balance type. Any row returned is a break in the chain (none for the seed data).
SELECT wallet_id, balance_type, wallet_txn_id, balance_before, prev_balance_after
FROM (SELECT wallet_id, balance_type, wallet_txn_id, balance_before,
             LAG(balance_after) OVER (PARTITION BY wallet_id, balance_type
                                      ORDER BY created_at_utc, wallet_txn_id) AS prev_balance_after
      FROM wallet_transactions) x
WHERE balance_before <> COALESCE(prev_balance_after, 0);

-- ---------------------------------------------------------------------------
-- (d) Deposits that failed, and the player later succeeded
--     "Later" is taken as within 24 hours (the same session or day). Only the first success after
--     each failure is returned. Uses ix_deposit_player_time.
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
 AND s.created_at_utc <= f.created_at_utc + INTERVAL 24 HOUR
WHERE f.status = 'failed'
  AND NOT EXISTS (
      SELECT 1 FROM deposit_attempts s2
      WHERE s2.player_id = f.player_id AND s2.status = 'success'
        AND s2.created_at_utc > f.created_at_utc AND s2.created_at_utc < s.created_at_utc
  )
ORDER BY f.created_at_utc;
