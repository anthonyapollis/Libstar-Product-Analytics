# Table inventory: what each table is, who creates it, and why

A fresh local setup creates **52 objects in 4 databases**:

- 29 base tables, loaded by one SQL script.
- 23 objects built by dbt: 11 views and 12 tables.

Nothing else is created. Every derived object comes from dbt, so there are no hand-built copies.
Row counts are from a fresh load plus `dbt build` on MariaDB 10.11.

| Layer | Database | Objects | Created by | Holds data? |
|---|---|---|---|---|
| Source (Ex 1, 2) | `jsb_assessment` | 6 tables | `local_load/01_load_submission_tables.sql` | yes |
| Source (Ex 3) | `jsb_platform` | 23 tables | the same script (`ddl.sql` + `seed.sql`) | yes |
| Staging | `jsb_platform_staging` | 11 views | `dbt run --select staging` | **no**: views read the base tables live |
| Marts | `jsb_platform_marts` | 12 tables | `dbt run --select marts` | yes, derived; rebuilt by every `dbt run` |

## Why dbt adds 23 objects on top of the 29
- **Staging views (11)** give every source one consistent, typed, renamed shape. Examples: the
  normalised gateway reference, and deposit amounts as decimals. Each model then reads staging,
  never raw tables, so a source change is fixed in one place. They're **views**, so they duplicate
  no data.
- **Mart tables (12)** are the reporting layer the brief asks for ("from operational design to a
  reporting model"):
  - a star schema for Exercise 3;
  - the reconciliation for Exercise 1 as a scheduled, tested model instead of a one-off script;
  - two marts answering Exercise 3's queries (a) and (b).

  Power BI reads these tables. They are materialised because they are what the report and the
  tests query.
- **The 44 dbt tests run on these objects.** Examples: the bridge residual must be exactly 0, no
  source row may be dropped, and the wallet balance cache must equal the ledger. That's the
  practical reason for doing the transformations in dbt rather than in ad-hoc SQL.

## Every object
### `jsb_assessment`: source data for Exercises 1 and 2 (6 tables)
| Table | Rows | Purpose |
|---|---:|---|
| `internal_deposits` | 326 | Ex 1 supplied file, loaded as-is |
| `gateway_settlement` | 306 | Ex 1 supplied file, loaded as-is |
| `transactions` | 1,024 | Ex 2 target table: API records, upserted by `id` |
| `ingest_checkpoint` | 1 | Ex 2 resume point (cursor) for restartable loads |
| `ingest_runs` | 3 | Ex 2 run log: monitoring and audit |
| `ingest_rejects` | 1 | Ex 2 quarantine: the bad record (TX000777) with its raw JSON, kept, not dropped |

### `jsb_platform`: Exercise 3 operational design (23 tables)
| Table | Rows | Purpose |
|---|---:|---|
| `players` | 3 | Player master (no PII) |
| `player_identity` | 3 | PII, split out so reporting never sees it |
| `player_vip_tier_history` | 4 | VIP tier over time (SCD2) |
| `player_tag_history` | 2 | Tags/segments over time |
| `affiliates` | 2 | Acquisition source |
| `wallets` | 3 | One per player and currency; balance cache |
| `wallet_transactions` | 10 | Append-only ledger: the source of truth for balances |
| `payment_methods` | 2 | Tokenised payment instruments |
| `deposit_attempts` | 4 | Every attempt, including failures |
| `withdrawal_requests` | 0 | Withdrawal workflow (empty in the sample data) |
| `bets` | 4 | One header per bet, all products |
| `sports_events` | 1 | Sportsbook reference data |
| `sports_bet_details` | 2 | Sportsbook-specific bet detail |
| `bet_legs` | 2 | Multi-leg (accumulator) selections |
| `game_providers` | 1 | Casino reference data |
| `games` | 1 | Casino reference data |
| `casino_round_details` | 1 | Casino-specific bet detail |
| `retail_locations` | 1 | Retail reference data |
| `devices` | 1 | Retail terminals |
| `retail_bet_details` | 1 | Retail-specific bet detail |
| `bonus_campaigns` | 1 | Campaign rules (rollover, min odds) |
| `player_bonuses` | 2 | Grants and their status |
| `bonus_rollover_events` | 1 | Event-sourced wagering progress |

### `jsb_platform_staging`: dbt staging views (11 views, no stored data)
`stg_players`, `stg_player_vip_tier_history`, `stg_wallet_transactions`, `stg_bets`,
`stg_deposit_attempts`, `stg_bonus_campaigns`, `stg_player_bonuses` (Ex 3);
`stg_internal_deposits`, `stg_gateway_settlement` (Ex 1); `stg_transactions`, `stg_ingest_runs` (Ex 2).

### `jsb_platform_marts`: dbt reporting tables (12 tables)
| Table | Rows | Purpose | Used by |
|---|---:|---|---|
| `dim_player` | 3 | Player dimension | Power BI |
| `dim_player_vip_tier_scd` | 4 | VIP tier history (Type 2) | Power BI |
| `dim_campaign` | 1 | Campaign dimension | Power BI |
| `dim_date` | 92 | Calendar | Power BI |
| `fact_bet` | 4 | One row per bet: GGR and NGR | Power BI |
| `fact_wallet_transaction` | 10 | One row per ledger movement: balances as of any date | Power BI |
| `fact_bonus_transaction` | 2 | One row per bonus grant: bonus cost | Power BI |
| `fct_recon_exceptions` | 317 | Ex 1: every deposit and settlement, categorised | Power BI, bridge test |
| `mart_recon_bridge` | 11 | Ex 1: bridge steps, internal total → gateway total | Power BI waterfall |
| `mart_recon_summary_by_category` | 13 | Ex 1: rows and rand per category for Finance | Finance summary |
| `mart_ngr_by_product_monthly` | 3 | Ex 3 query (a) as a table | Cross-check of the DAX |
| `mart_bonus_cost_pct_of_ngr` | 1 | Ex 3 query (b) as a table | Cross-check of the DAX |

## Not created by the setup, on purpose
- **`jsb_assessment.recon_exceptions`** is written by the standalone Exercise 1 script
  `exercise1-reconciliation/sql/03_reconciliation.sql` only when someone runs that script by hand.
  It holds the same 317 rows as `fct_recon_exceptions`, so the setup doesn't run it. The dbt model
  is the one to keep. The script stays in the repo as the Exercise 1 SQL answer, and
  `04_independent_check.py` compares the two.
- **No backups or copies.** Codex took the backup of the old builds before removing them, and it
  lives outside the database on the user's machine.
