# Power BI — JSB data model and report

`Demo.pbix` (the file you sent) is currently a blank template: empty data model,
one report page, zero visuals. I can't write into it directly — the `DataModel`
part inside a `.pbix` is a proprietary compressed binary (xVelocity/Analysis
Services) format that only Power BI Desktop (or the AS engine, Windows-only)
can produce correctly; there's no tool in this Linux container that can safely
generate or edit it. Writing a corrupt one would just fail to open.

What's here instead gets you a finished model in a few minutes of clicking,
with **no database connection required** — everything loads from CSV, which
sidesteps the exact localhost/proxy problem we spent this session fixing in
Postman.

## What's in this folder
| File | What it is |
|---|---|
| `model.png` / `model.mmd` | The star schema to build: 3 dimensions, 3 facts, exactly matching `dbt_jsb_assessment/models/marts/` |
| `data/*.csv` | The actual mart data, exported from the dbt build (small seed dataset — enough to prove the model and measures work; swap in full-volume CSVs later the same way) |
| `measures.dax` | Every DAX measure, ready to paste in |

## Steps in your Power BI Desktop
1. Open `Demo.pbix`.
2. **Get Data → Text/CSV** → import each file in `data/` as its own table (9 tables total: `dim_player`, `dim_player_vip_tier_scd`, `dim_campaign`, `dim_date`, `fact_bet`, `fact_wallet_transaction`, `fact_bonus_transaction`, `mart_ngr_by_product_monthly`, `mart_bonus_cost_pct_of_ngr`). Power BI will infer types automatically; double-check `date_day`/`placed_date`/`transaction_date` columns come in as **Date**, not text.
3. Go to **Model view** (left rail, the 3-box icon). Drag to create the relationships shown in `model.png`:
   - `dim_player.player_id` → `fact_bet.player_id` (1 → many)
   - `dim_player.player_id` → `fact_wallet_transaction.player_id` (1 → many)
   - `dim_player.player_id` → `fact_bonus_transaction.player_id` (1 → many)
   - `dim_player.player_id` → `dim_player_vip_tier_scd.player_id` (1 → many)
   - `dim_date.date_day` → `fact_bet.placed_date` (1 → many)
   - `dim_date.date_day` → `fact_wallet_transaction.transaction_date` (1 → many)
   - `dim_campaign.campaign_id` → `fact_bonus_transaction.campaign_id` (1 → many)
   - `fact_bet.bet_id` → `fact_wallet_transaction.related_bet_id` (1 → many)
   - `fact_bonus_transaction.player_bonus_id` → `fact_wallet_transaction.related_player_bonus_id` (1 → many)
4. **Modeling → New Measure**, paste each block from `measures.dax` one at a time (they reference each other, so add them in the order listed).
5. Back in **Report view**, Page 1: drop a few cards/a table — `[NGR]` and `[Bonus Cost % of NGR]` by `fact_bet[product]` reproduces Exercise 3's example query (a); slice `fact_bonus_transaction` by `dim_campaign[campaign_name]` for query (b).

## When you're ready for full volume
The `data/` CSVs here come from the same seed dataset used to verify
`example_queries.sql` (3 players, 4 bets — enough to prove the model, not a
real report). To scale up: point the dbt project at a fuller dataset (or load
Exercise 1/2's actual CSVs into the operational schema), rerun `dbt build`,
and re-export the mart tables the same way (`SELECT * FROM <mart> INTO
OUTFILE`, or the same Python/pymysql export used here) — the model and DAX
measures don't change, only the row counts do.
