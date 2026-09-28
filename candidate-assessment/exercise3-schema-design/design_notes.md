# Exercise 3 — Design notes

**Tools used:** MySQL 8.0 (DDL, ran and verified — see `ddl.sql`, `seed.sql`), Mermaid (ERD, rendered
to `erd.png`), dbt (reporting layer sketch, see `../dbt_jsb_assessment/`).

## Money and time
- **Money:** `DECIMAL(18,4)` everywhere a balance or amount is stored — never `FLOAT`/`DOUBLE`. Gambling
  finance needs exact arithmetic (a balance that's off by a rounding error is a control failure, not a
  cosmetic bug); `DECIMAL` guarantees that. 4 decimal places gives headroom for odds-derived payouts
  and any future multi-currency FX work without re-migrating the column.
- **Time:** `DATETIME(6)`, always UTC, columns suffixed `_at_utc`. I deliberately avoided MySQL's
  `TIMESTAMP`, which silently converts using the session/server time zone — exactly the kind of
  behaviour that turns "what time did this bet settle" into a debugging session. Storing UTC
  everywhere and deriving Windhoek (or any other market's) local time in the reporting layer keeps the
  source of truth unambiguous, which matters for GGR cut-off, settlement timing and fraud velocity
  checks alike.

## How a balance is calculated, and how it's guaranteed correct
`wallets.real_balance` / `bonus_balance` are a **cache**, not the source of truth. The source of truth is
`wallet_transactions`: an append-only ledger where every deposit, withdrawal, stake, win, bonus
movement, refund and manual adjustment is one row, and a balance at any moment is
`SUM(credit) - SUM(debit)` up to that moment (see `example_queries.sql`, query (c), which reconstructs
player 1's balance at a point in time and gets exactly the value the running cache would show).

Three things make this trustworthy:
1. **Never edit, only append.** A correction or a chargeback is a new row with `reversal_of_wallet_txn_id`
   pointing at the original. The ledger can reproduce exactly what any balance was on any past date —
   what an auditor asks for, and what an UPDATE-in-place table can never give you back.
2. **Idempotency key on every row** (`idempotency_key`, unique). Whatever produced the event —
   a payment webhook, a bet settlement, a retried job — carries a deterministic key
   (`source_system + source_event_id`, or a hash of immutable business fields). Loading is always an
   upsert against that key, so replaying an event, or receiving it twice, can never double-post it. This
   is the same idempotency-key principle behind Exercise 2's ingestion and Exercise 1's reconciliation
   breaks (duplicate deposit/duplicate settlement) — one discipline, three places it pays off.
3. **The cache is only ever written by the same procedure/transaction that writes the ledger row**
   (`balance_before`/`balance_after` captured on the ledger row itself). A scheduled job periodically
   recomputes `SUM(wallet_transactions)` per wallet and compares it to the cached balance; a mismatch
   is a P1 alert — the cache is convenience, the ledger is truth, and the two must never silently
   diverge.

## Keeping history where things change over time
`player_vip_tier_history` and `player_tag_history` are SCD Type 2: a new row with `valid_from_utc` on
every change, `valid_to_utc` set (NULL = current) rather than an UPDATE. `players.vip_tier` keeps the
current value inline for fast reads (every bet/wallet query needs "what tier is this player right now"),
while the history table answers "what tier were they on 3 September" for VIP and marketing analysis, or
for reconstructing what promotion eligibility looked like at the time a bonus was granted. The same
pattern extends to anything else that needs to be provably point-in-time correct (KYC status, risk
segment) without restructuring the model.

## Protecting personal information while still supporting analysis
- **Identity is a separate table** (`player_identity`), joined 1:1 to `players` only by `player_id`. Every
  other table — bets, wallet transactions, bonuses — references `player_id`, never a name or ID number.
  An analyst building a GGR-by-VIP-tier dashboard never needs to touch `player_identity` at all.
- **Column-level protection** on the identity table: `national_id_number` stored as `VARBINARY`
  (application-layer encrypted before it reaches MySQL; the key lives in a KMS, not in the database), a
  dedicated low-privilege DB role that is the only grantee on `player_identity`, and every read of it
  logged (who, when, which player) — the same "who saw identity data" audit principle used for the
  restricted tier in the reporting layer.
- **Masked views for analysts:** where a workflow genuinely needs a partial identifier (e.g. confirming a
  KYC document matches a name), expose it through a view that returns a masked value
  (`CONCAT(LEFT(first_name,1), '***')`) rather than granting table access.
- **Retention:** PII fields carry their own retention/erasure policy independent of the behavioural
  data they're separated from, so a "right to be forgotten" request doesn't require touching bet or
  wallet history at all.

## Answering the four questions (`example_queries.sql`, run against `seed.sql`)
All four ran successfully against MySQL 8.0 with the seed data loaded; output captured in
`evidence/example_queries_output.txt`.
- **(a) NGR by product for a month** — `bets` grouped by `product`, `stakes - payouts` for GGR, minus
  bonus stakes that were actually lost (realised bonus cost) for NGR. *Assumption, stated per the
  brief's instruction not to stop on ambiguity:* no regulatory levy is modelled since none was specified;
  a real deployment adds that line once the jurisdiction is confirmed.
- **(b) bonus cost as % of NGR, by campaign** — `player_bonuses.granted_amount` recognised as cost only
  once a grant *resolves* (completed/expired/forfeited); an `active` grant is a liability
  (`bonus_liability_outstanding`), not yet a cost — divided by total NGR for the period.
- **(c) a player's balance at a given date/time** — `SUM` over `wallet_transactions` up to the timestamp;
  proves the ledger, not a mutable column, is what "the balance" actually means.
- **(d) deposits that failed then later succeeded** — self-join on `deposit_attempts` (the same shape of
  table Exercise 1 reconciles against the gateway) matching a `failed` attempt to the next `success` for
  the same player within a bounded window.

## From operational design to a reporting model
The tables here are optimised for one row per business event, written by the application. A reporting
model asks different questions at different volumes, so it gets its own layer rather than reusing these
tables directly:
- **Bronze/raw:** land `wallet_transactions`, `bets`, `deposit_attempts`, etc. as append-only extracts,
  exactly as OLTP wrote them.
- **Silver/staging (dbt):** typed, deduplicated, one dbt model per source table — see
  `../dbt_jsb_assessment/models/staging/`.
- **Gold/marts (dbt):** a star schema — conformed dimensions (`dim_player`, `dim_game`, `dim_campaign`,
  `dim_date`) surrounding grain-specific facts (`fact_bet`, `fact_wallet_transaction`,
  `fact_bonus_transaction`) — see `../dbt_jsb_assessment/models/marts/`. Money facts carry the same
  idempotency/source-lineage columns as the OLTP ledger, and `dim_player` uses the same SCD2 pattern as
  `player_vip_tier_history` so "GGR by VIP tier as it stood at the time of the bet" is answerable
  correctly, not just "as it stands today". This mirrors the star-schema approach I've used for JSB
  previously (`dim_customer`/`fact_wallet_transaction`/... in the attached platform ebook) — one modelling
  discipline from OLTP through to the BI layer, not two different ones that drift apart.
