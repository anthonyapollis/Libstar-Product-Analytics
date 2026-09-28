# dbt reporting layer — jsb_assessment

One dbt project spanning **all three exercises**, not just Exercise 3: the star-schema reporting model
("from operational design to a reporting model") plus Exercise 1's reconciliation as a scheduled model
instead of a one-off script — the automation Exercise 1's `summary.md` describes in prose, made real
and testable.

**Tools:** dbt-core 1.7 + dbt-mysql, MySQL 8.0.

## Layout
```
models/
  staging/   one view per operational table, across TWO source databases:
               jsb_platform    -> players, wallets, bets, bonuses (Exercise 3)
               jsb_assessment  -> internal_deposits, gateway_settlement (Exercise 1),
                                  transactions + ingest_runs (Exercise 2, staged for
                                  consistency -- ingest.py still owns the actual EL,
                                  dbt is T-only)
  marts/     dim_player, dim_player_vip_tier_scd (Type 2), dim_campaign, dim_date,
             fact_bet, fact_wallet_transaction, fact_bonus_transaction,
             fct_recon_exceptions + mart_recon_summary_by_category + mart_recon_bridge
             (Exercise 1's categorisation logic and bridge, portable and schedulable),
             + two reusable marts answering Exercise 3's example queries (a) and (b)
tests/
  assert_recon_bridge_reconciles.sql      -- the R0.00-residual bridge, enforced as code
  assert_recon_covers_all_sources.sql     -- no source row silently dropped
  assert_wallet_cache_matches_ledger.sql  -- cached wallet balances = sum of the ledger
```
Grain is kept deliberately narrow per fact (one bet, one ledger movement, one bonus grant) rather than
one wide "transactions" table — see `dbt_jsb_assessment/models/marts/fact_bet.sql`'s header comment and
`exercise3-schema-design/design_notes.md`.

## Run it
```bash
# schema + seed data must exist first (see ../exercise3-schema-design/)
mysql -u <user> -p < ../exercise3-schema-design/ddl.sql
mysql -u <user> -p jsb_platform < ../exercise3-schema-design/seed.sql

pip install dbt-mysql
export DBT_PROFILES_DIR=.       # profiles.yml lives in this directory
dbt debug
dbt build                       # runs models + all tests
```

`evidence/dbt_build_output.txt` has a captured run: **66/66 PASS, 0 errors** (23 models, 43 tests).

## Notes
- `player_identity` (PII) is deliberately not a dbt source — see `models/staging/_staging.yml`. The
  reporting layer only ever sees `player_id`.
- The two singular tests under `tests/` are the real payoff of moving Exercise 1 into dbt: run
  `dbt test -s assert_recon_bridge_reconciles` any morning after the day's files land, and a non-zero
  residual (a coding error, a new exception category nobody categorised, a source that changed shape)
  fails the build instead of silently producing a wrong number on a dashboard.
- `dbt docs generate` currently errors on this dbt-mysql version when sources span more than one MySQL
  database/schema (a known adapter limitation, unrelated to the models themselves); `dbt build`, the
  actual deliverable, is unaffected and fully green.
