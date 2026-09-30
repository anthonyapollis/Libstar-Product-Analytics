# Exercise 3: design notes

The answers follow the brief's seven tasks, in order. Everything here was run on MariaDB 10.11:
- `ddl.sql`, `seed.sql`, `ledger_posting.sql` and `example_queries.sql`;
- `test_ledger_posting.py`, which passes all 17 checks.

The SQL was run on MariaDB 10.11 and 10.4 (XAMPP). It is written to MySQL-compatible syntax; CHECK constraints are enforced by MariaDB 10.2+ (and by MySQL from 8.0.16, not tested here).

## 1. Tables, keys, types, constraints and indexes (`ddl.sql`, 24 tables)

| Area | Tables |
|---|---|
| Players | `players` (no personal data), `player_identity` (personal data only), `affiliates`, `player_vip_tier_history`, `player_tag_history`, `player_status_history` |
| Wallets | `wallets` (balance cache), `wallet_transactions` (the ledger), `payment_methods`, `deposit_attempts`, `withdrawal_requests` |
| Bets | `bets` (one header per bet, every product): <br>• sportsbook: `sports_bet_details`, `bet_legs`, `sports_events` <br>• casino: `casino_round_details`, `games`, `game_providers` <br>• retail: `retail_bet_details`, `retail_locations`, `devices` |
| Bonuses | `bonus_campaigns` (trigger, audience, rollover multiple, minimum odds, maximum stake, expiry), `player_bonuses` (grant, progress, outcome), `bonus_rollover_events` (each bet's contribution) |

- **Grain.** One header row per bet, with one detail table per product, so:
  - a sports leg, a casino round and a retail ticket each keep their own columns;
  - "all bets" is still one table.

  An accumulator is one `bets` row with one `bet_legs` row per selection:
  - `ck_sportsdet_legs` requires 1 leg for a single and at least 2 for an accumulator.
  - `uq_leg_bet_event_market` stops the same selection being added twice.
- **Real money, bonus money, or both.** A bet stores two stake columns:
  - `stake_real_amount` and `stake_bonus_amount`;
  - `total_stake` is generated from them.

  `bets.player_bonus_id` records which grant paid the bonus part. `ck_bets_bonus_funding` enforces "a bonus stake if and only if a grant". That link is what lets query (b) charge bonus cost to a campaign.
- **Keys.**
  - Every table has a primary key: surrogate `BIGINT` for high-volume tables, `INT` for small reference tables.
  - Every relationship has a declared foreign key.
- **Natural keys are unique, so a retry can't create a duplicate:**
  - `wallet_transactions.idempotency_key`
  - `bets.request_id` and `withdrawal_requests.request_id`
  - `deposit_attempts.gateway_ref`. Exercise 1 found duplicates exactly where this key was missing.
  - one wallet per player and currency
  - one reversal per ledger row
  - `(provider round)`, `(location, ticket)`, `(bonus, bet)` for rollover
- **Money.** `DECIMAL(18,4)`, never `FLOAT`/`DOUBLE`.
  - Binary floating point can't hold 0.10 exactly, and a balance that's off by a rounding error is a control failure.
  - Four decimals leave room for odds-derived payouts and FX. Amounts are rounded to 2 decimals for display only.
  - Currency is `CHAR(3)` on the wallet and the payment rows: `NAD` today.
  - Odds are `DECIMAL(10,3)`.
- **Time.** `DATETIME(6)`, always UTC, with columns named `*_at_utc`.
  - MySQL's `TIMESTAMP` converts through the session time zone, so the same row can read differently on two connections.
  - Microseconds keep the order of events that happen in the same second, such as a stake and its bonus part.
  - Local (Windhoek) time is derived in the reporting layer.
- **Constraints.**
  - ENUMs for closed lists: bet status, transaction type, bonus outcome, and player status (active, blocked, self-excluded, closed).
  - CHECKs for single-row rules:
    - amounts > 0;
    - `balance_after = balance_before ± amount`;
    - a reversal must point at the row it reverses;
    - a manual adjustment or reversal needs a reason;
    - settled bets need a settlement time;
    - a resolved bonus needs a resolution time;
    - SCD periods must end after they start;
    - odds > 1.
  - Rules that span rows are enforced by the posting procedures (§3).
- **The most important indexes, each for a named access path:**
  - `(wallet_id, created_at_utc)` and `(player_id, created_at_utc)`: balance at a point in time, query (c);
  - `(product, settled_at_utc)`: NGR by month, query (a);
  - `(player_id, created_at_utc)` on deposits: query (d);
  - `(player_id, placed_at_utc)`: player history and responsible-gambling checks;
  - `player_bonus_id` on bets and ledger: query (b);
  - `(player_id, valid_to_utc)` on each history table: the current row.

## 2. ERD and SQL
- `erd.png`: rendered from `erd.mmd` (Mermaid, so it's diff-able and regenerated from source).
- `ddl.sql`: the `CREATE TABLE` statements.
- `seed.sql`: fictitious data that exercises every relationship. It includes:
  - an accumulator;
  - a split real/bonus stake;
  - a forfeited bonus;
  - a correction.

## 3. How a balance is calculated, and how it's guaranteed correct
**A balance is the sum of the ledger.** `wallet_transactions` is append-only:
- Every movement is one row: deposit, withdrawal, stake, win, bonus credit or debit, refund, reversal, manual adjustment.
- Each row has an `amount > 0`, a direction and a balance type (real or bonus).
- The balance at time T is `SUM(credit − debit) WHERE created_at_utc <= T` (query (c)).
- `wallets.real_balance` and `wallets.bonus_balance` are a cache of that sum, for fast reads.

**What makes it provable:**
1. **Only two procedures move money** (`ledger_posting.sql`). The application gets `EXECUTE` on them and no write access to the two tables. `post_wallet_txn`, in one transaction:
   - locks the wallet row (`FOR UPDATE`);
   - checks the idempotency key, so a replayed event returns the original row and posts nothing;
   - refuses a debit larger than the balance;
   - writes the ledger row with `balance_before`/`balance_after`;
   - sets the cache to `balance_after`.

   The ledger and the cache therefore can't disagree, and two postings to one wallet can't read the same starting balance. The test posts 20 concurrently and checks the chain.
2. **The chain is self-checking.** Each row's `balance_before` must equal the previous row's `balance_after` in the same wallet and balance type. `ck_wtxn_balance_math` checks each row, and the chain query in `example_queries.sql` checks the sequence.
3. **An independent daily control.** It recomputes every wallet from the ledger and compares it with the cache. It's a dbt test here: `assert_wallet_cache_matches_ledger` fails the build on any difference. Any difference is an incident; it is never silently corrected.

**Corrections and reversals are new rows; nothing is ever updated or deleted.**
- **Reversal:** `reverse_wallet_txn` posts an equal and opposite row:
  - `txn_type = 'reversal'`, `reversal_of_wallet_txn_id` = the original, with a mandatory reason and `created_by`;
  - the unique key on `reversal_of_wallet_txn_id` means a row can only be reversed once;
  - the original is untouched, and "reversed" is derived: some row points at it.
- **Correction:** reverse the wrong row, then post the right one. The seed does exactly this:
  - an agent keyed a 50.00 goodwill credit instead of 15.00;
  - query (c) returns 450.00 between the error and the reversal, and 415.00 after.

  An auditor can see what the balance was, what was wrong, who fixed it and why.
- **Void or refunded bet:** a `refund` row linked to the bet. A chargeback on a deposit is a reversal of the deposit row.

There's no status column on the ledger because a status would have to be updated. An earlier draft had one, and filtering on it would have counted a reversal without the row it cancels.

## 4. History where things change over time
- **SCD Type 2 tables:** `player_vip_tier_history`, `player_tag_history`, `player_status_history` (account status and KYC together).
  - A change closes the current row (`valid_to_utc`) and opens a new one (`valid_from_utc`, `changed_by`, reason).
  - `NULL` in `valid_to_utc` means "current".
  - Tags are many-at-once, so that table is keyed per player, tag and start.
- `players` keeps the current tier and status inline, because most reads want "now". The history tables answer the point-in-time questions:
  - VIP/marketing: "what tier was this player in on 3 September?"
  - Regulator: "was this player self-excluded or unverified when the bet was placed?"
- **Other history needs no extra table:**
  - money history is the ledger itself;
  - bonus progress is `bonus_rollover_events`;
  - campaign rules are versioned by `valid_from_utc`;
  - a grant also copies `rollover_required` at grant time, so a later rule change can't rewrite an old bonus.

## 5. Protecting personal information and still supporting analysis
- **Separation.** Personal data lives only in `player_identity`: name, date of birth, national ID, email, phone, address.
  - Every other table carries only `player_id`, a meaningless surrogate.
  - Analysis never needs identity: GGR by VIP tier, cohort by affiliate, bonus cost by campaign all work on `player_id`.
  - The dbt project doesn't even declare `player_identity` as a source.
- **Access.** One restricted role can read `player_identity`, and every read is logged (who, when, which player). Analysts have no grant on it.
  - Where a workflow needs a partial identifier, a view returns a masked value, e.g. `CONCAT(LEFT(first_name, 1), '***')`.
  - If analysis needs age or region, they are published as bands (`age_band`, `region`), never dates of birth or addresses.
- **Encryption.**
  - The national ID is encrypted in the application before it reaches the database (`VARBINARY`). The key is in a KMS, not the database.
  - Disk and backups are encrypted.
  - In the warehouse, a keyed hash of the player ID can replace the ID for data shared outside the team.
- **Retention and erasure.** Personal data has its own retention period. Erasure removes or anonymises the `player_identity` row. Bets and ledger rows stay intact for financial and regulatory retention, keyed only by `player_id`.

## 6. The four questions (`example_queries.sql`, output in `evidence/example_queries_output.txt`)
Definitions (assumptions, written down):
- **GGR** = stakes − payouts on bets settled in the month (won or lost).
- **Bonus cost** = the bonus money wagered on those bets.
- **NGR** = GGR − bonus cost, which is real-money stakes − payouts.

Why this definition of bonus cost:
- Bonus money isn't revenue.
- A win on a bonus-funded bet is already in payouts, so converting bonus winnings to cash later isn't counted twice.
- An unwagered bonus that expires or is forfeited costs nothing: the seed's forfeited grant costs 0.00.
- The unwagered balance of an active grant is a liability, not yet a cost.

No levy or tax line is modelled; the brief doesn't give one. The same definition is used in the dbt marts, Power BI and Databricks.

| | How | Seed result (September 2026) |
|---|---|---|
| (a) NGR by product for a month | `bets` settled in the month, grouped by product | casino 270.00, retail 100.00, sportsbook −150.00; total 220.00 |
| (b) Bonus cost as % of NGR by campaign | Bonus stakes → the grant that paid them (`bets.player_bonus_id`) → campaign, ÷ the month's total NGR | Registration Bonus: 40.00 = 18.18% |
| (c) Balance at a date and time | Sum of the ledger up to that moment, reversals included | player 1 at 2026-09-06 00:00: 1,160.00; player 2: 450.00 at 09:15, 415.00 after the correction |
| (d) Failed deposit, then a success | Self-join on `deposit_attempts`: the first success by the same player within 24 hours of a failure | player 2: failed 09:00, succeeded 09:04 (4 minutes) |

## 7. From this design to a reporting model
The operational tables are shaped for writing one business event at a time. Dashboards need a star schema, built in dbt (`../dbt_jsb_assessment/`):
- staging views clean and type each source;
- marts are materialised tables with keys and tests.

- **Facts, each at one stated grain:**
  - `fact_bet`: one row per bet, with GGR, bonus cost, NGR and the campaign that paid the bonus part.
  - `fact_wallet_transaction`: one row per ledger movement; loaded incrementally, because the ledger is append-only.
  - `fact_bonus_transaction`: one row per grant, with bonus cost and the outstanding liability.
- **Dimensions:** `dim_player`, `dim_player_vip_tier_scd`, `dim_campaign`, `dim_date`, and product.
  - `fact_bet` joins the VIP tier *as it was when the bet was placed*.
  - Personal data never enters the model.
- **Summary marts** for the two finance questions: `mart_ngr_by_product_monthly`, `mart_bonus_cost_pct_of_ngr`.
- **Tests on every build:** unique and not-null keys; ledger equals cache.

Power BI reads the marts (`../powerbi/`). At volume, the facts would be partitioned by month and loaded incrementally from a CDC feed of the operational database.
