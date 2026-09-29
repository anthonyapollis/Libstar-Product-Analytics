# Schema requirements traceability

This record distinguishes what the candidate brief explicitly requires from the table-level implementation choices. The brief names business capabilities rather than prescribing table names. A table is retained only when it preserves a required fact, history, control, or reporting grain. It is not retained merely because it appeared in an earlier build.

## Decision rule

1. **Direct requirement** — the brief names the entity, event, or result.
2. **Necessary normalisation** — the table separates an explicitly required relationship or product-specific detail so keys, constraints, and reporting remain reliable.
3. **Operational control** — the table proves restartability, preserves rejected data, or records a financial event required for audit.
4. **Derived reporting** — a dbt object exists for a requested dashboard/reporting question; it does not replace source history.

No table is classified as an unexplained extension. If a future scope removes the underlying requirement, the corresponding table should be reviewed before deployment.

## Exercises 1 and 2 — six source/control tables

| Table | Classification | Brief basis | Why it remains |
|---|---|---|---|
| `internal_deposits` | Direct | supplied reconciliation file | Raw internal record; reconciliation must preserve the file as supplied. |
| `gateway_settlement` | Direct | supplied settlement file | Raw gateway record; holds fee, net, status, and settlement time. |
| `transactions` | Direct | “load all transactions into a table” | Canonical, de-duplicated API target. |
| `ingest_checkpoint` | Operational control | restart safely at any point | Stores the last fully committed position. |
| `ingest_runs` | Operational control | monitor rows loaded/rejected, duration, and last success | Immutable run-level monitoring and failure evidence. |
| `ingest_rejects` | Operational control | bad records must not be lost silently | Quarantine with reason and raw payload; intentionally not a duplicate of valid transactions. |

## Exercise 3 — 24 operational tables

| Area | Tables | Classification | Brief basis and validation |
|---|---|---|---|
| Player, privacy and history | `players`, `player_identity`, `affiliates`, `player_vip_tier_history`, `player_tag_history`, `player_status_history` | Direct requirement + history implementation | The brief requires registration, KYC, tags, VIP tier, traffic source/affiliate, status, sensitive-data protection, and history where tags/VIP change. `player_status_history` is also direct in substance: the brief explicitly lists active/blocked/self-excluded status and asks for regulator queries; an SCD2 history is necessary to answer status/KYC **at bet time**. |
| Wallet and payment lifecycle | `wallets`, `wallet_transactions`, `payment_methods`, `deposit_attempts`, `withdrawal_requests` | Direct requirement + necessary normalisation | The brief requires real/bonus balances plus deposits, withdrawals, bets, wins, bonuses, refunds, reversals, adjustments, and provable historical balances. The append-only ledger is the proof; payment methods identify the instrument without storing raw card details. |
| Sports, casino and retail bets | `bets`, `sports_events`, `sports_bet_details`, `bet_legs`, `game_providers`, `games`, `casino_round_details`, `retail_locations`, `devices`, `retail_bet_details` | Direct requirement + necessary normalisation | The brief explicitly requires single/accumulator legs, odds/settlement, casino game/provider/round, and retail location/device. Separate product detail tables prevent incompatible nullable columns and allow product NGR reporting. |
| Bonuses | `bonus_campaigns`, `player_bonuses`, `bonus_rollover_events` | Direct requirement + history implementation | The brief requires campaign rules, grants, rollover progress, and completed/expired/forfeited outcomes. Event-sourced rollover records preserve progress; grant status and resolution time store the outcome without inventing a duplicate outcome table. |

## dbt objects — reporting, not duplicate source structures

| Layer | Count | Why it exists |
|---|---:|---|
| Staging views | 11 views | Typed, named source interface. Views store no duplicate data. |
| Reporting marts | 13 tables | Facts/dimensions plus requested reconciliation, NGR, bonus-cost, and API-monitoring answers. Two are incremental where the source grain supports it. |

After the fresh local build there are **30 base tables + 13 mart tables + 11 staging views = 54 objects**. The 43 physical tables and 11 views are expected layers of one design, not competing duplicate implementations.

## Explicit validation outcome

- `player_status_history` is **retained**: it implements explicit status/KYC and the brief’s history/regulator-query requirement.
- `payment_methods`, product reference/detail tables, and `bonus_rollover_events` are **retained**: they normalise named business concepts and support auditable keys, constraints, and required reporting.
- `ingest_checkpoint`, `ingest_runs`, and `ingest_rejects` are **retained**: they are required controls for restartability, monitoring, and non-silent handling of bad data.
- No separate bonus-outcome table is required: `player_bonuses.status` and `resolved_at_utc` represent completed, expired, and forfeited outcomes.
- Raw Exercise 1 duplicate rows remain intentionally because finding them is the reconciliation task; they are data-quality exceptions, not duplicate tables.