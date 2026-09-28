# dbt reporting layer — jsb_assessment

The star-schema reporting model referenced in Exercise 3's design notes ("from operational design to a
reporting model"), built with dbt against the Exercise 3 MySQL schema (`jsb_platform`).

**Tools:** dbt-core 1.7 + dbt-mysql, MySQL 8.0.

## Layout
```
models/
  staging/   one view per operational table: typed, renamed, no business logic
  marts/     dim_player, dim_player_vip_tier_scd (Type 2), dim_campaign, dim_date,
             fact_bet, fact_wallet_transaction, fact_bonus_transaction,
             + two reusable marts answering Exercise 3's example queries (a) and (b)
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

`evidence/dbt_build_output.txt` has a captured run: **46/46 PASS, 0 errors** (16 models, 30 tests).

## Notes
- `player_identity` (PII) is deliberately not a dbt source — see `models/staging/_staging.yml`. The
  reporting layer only ever sees `player_id`.
- `dbt docs generate` currently errors on this dbt-mysql version when sources span more than one MySQL
  database/schema (a known adapter limitation, unrelated to the models themselves); `dbt build`, the
  actual deliverable, is unaffected and fully green.
