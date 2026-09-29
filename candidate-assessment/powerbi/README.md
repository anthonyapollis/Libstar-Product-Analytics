# Power BI — JSB reporting model and report

A finished Power BI project covering all three exercises. The semantic model has 11 tables,
7 relationships and 28 DAX measures (22 calculations and 6 colour rules for the KPI tiles), and the report has four pages. **The data is embedded in the
project**, so it opens and refreshes on any machine with no folder path to set.

## Open it
1. Unzip into a **new, empty folder**. Don't unzip over an older copy: Power BI would keep the old
   data. Close any older copy of `JSB_Assessment` first.
2. In Power BI Desktop: **File → Open → `JSB_Assessment.pbip`**, then **Refresh**.
   (Older Desktop versions: first enable *Options → Preview features → Power BI Project (.pbip) save option*.)
3. Check the visuals against `expected_values.md`. The quick test that you have the current
   version is Page 1: **GGR 260.00 · Bonus Cost 40.00 · NGR 220.00 · Liability 10.00**, and
   18.18% in the campaign table. Page 4 shows **4** ingestion runs. If you see GGR −70.00 or
   3 runs, it's an old copy.

## Pages
| Page | What it shows |
|---|---|
| NGR overview (Ex. 3) | GGR, realised bonus cost, NGR and bonus liability cards; GGR vs NGR by product; bonus cost as % of NGR by campaign |
| Player balances (Ex. 3) | Date slicer, deposits, and each player's balance rebuilt from the ledger as of the slicer's end date |
| Reconciliation (Ex. 1) | Settlements matched exactly (274), exceptions (43), act-now value (R3,150), bridge residual (R0.00); the bridge as a waterfall from R218,280.00 to R217,979.97; exceptions by category; detail table |
| Ingestion monitoring (Ex. 2) | Transactions loaded (1,024), runs, rows rejected, rate-limit retries; run history, including the run killed mid-page; transactions by status |

## Look
- A navy title bar on each page, a light grey page background, and white chart panels with rounded borders.
- **KPI tiles.** Status tiles follow their own value through a colour measure: green when fine,
  amber when something needs a look, red when action is needed. These are GGR, NGR, Exceptions,
  Act Now Value, Bridge Residual and Rows Rejected. Informational tiles have a fixed colour that
  fits their meaning: amber for bonus cost, purple for bonus liability, green for deposits and
  loaded rows, navy for runs, teal for handled retries. The expected colour of every tile is in
  `expected_values.md`.
- **Charts.** Exceptions are coloured by type (break red, timing amber, reversal purple, rounding
  grey). The waterfall shows increases green, decreases red and totals navy. Transaction statuses
  are coloured completed green, failed red, pending amber, reversed purple.

## What's in the folder
| File | What it is |
|---|---|
| `JSB_Assessment.pbip` | The project file you open |
| `JSB_Assessment.SemanticModel/model.bim` | Tables, Power Query, relationships, DAX measures |
| `JSB_Assessment.Report/report.json` | The four report pages |
| `data/*.csv` | The dbt marts and staging tables the model is built from |
| `model.png` | The Exercise 3 star schema |
| `measures.dax` | Every measure, readable |
| `expected_values.md` | What each visual should show, computed independently with pandas |
| `build_pbip.py` | Generates all of the above from one set of definitions and validates it. `--folder` reads the CSVs from a folder parameter instead of embedding them, for full-volume data |

## Model design
- **Star schema.** `dim_player`, `dim_date` and `dim_campaign` filter the three facts. Filters
  flow one way, from dimension to fact.
- **Facts are not joined to each other.** `fact_wallet_transaction.related_bet_id` and
  `related_player_bonus_id` stay as drill-through keys, not relationships. Joining facts to facts
  would give `dim_player` two filter paths to the wallet table, and Power BI rejects an ambiguous
  model. `build_pbip.py` checks every pair of tables and refuses to build if any pair has more
  than one filter path.
- **Money is fixed decimal** (`Currency.Type`, four decimal places, matching `DECIMAL(18,4)` in
  MySQL). CSVs are parsed with `en-US` culture, so a South African regional setting (comma
  decimal separator) doesn't misread `200.0000`.
- **The Exercise 1 and 2 tables stand alone.** They share no keys with the player model, so they
  have no relationships to it, and filters on one page can't leak into another.
- **Measures follow the SQL definitions** in `exercise3-schema-design/example_queries.sql`:
  - NGR = GGR − bonus cost, where bonus cost is the bonus money wagered on settled bets (query a).
  - Campaign bonus cost is the bonus money wagered from that campaign's grants, divided by total
    NGR (query b). The bonus liability is the unwagered part of active grants.
  - Balance as of a date is the sum of the ledger up to that date, reversals included (query c).

## How it was verified, and the limit of that
No Power BI Desktop runs in this Linux build environment, so the project could not be opened
there. What was checked:
- `build_pbip.py` validates that every visual field, sort and measure reference resolves to the
  model, that every CSV's columns match the model, that every relationship column exists, and that
  there are no ambiguous filter paths. A negative
  test confirmed it catches an ambiguous relationship and a misspelled measure or column.
- `expected_values.md` is computed from the CSVs in pandas, independently of the DAX. It matches
  the MariaDB query results and the dbt marts: NGR 220.00 (sportsbook −150.00), bonus cost
  40.00 = 18.18% of NGR, liability 10.00, and player 1's balance of 1,160.00 on 2026-09-06.
- The report format mirrors the layout in the supplied `Demo.pbix`: Power BI Desktop 2.130,
  CY24SU06 theme.

Power BI Desktop has since opened an earlier version of this project, with the same format and
report layout: both pages and all visuals loaded. The one failure was the data folder path, which
the embedded data now removes.

If Desktop reports a problem opening the project, the manual route below builds the same model in a
few minutes.

## Manual route (fallback)
1. Open `Demo.pbix` → **Get Data → Text/CSV** → import the seven `dim_*` / `fact_*` CSVs.
2. **Model view**, create the relationships (the many-side column is listed first):
   `fact_bet.player_id → dim_player.player_id` · `fact_wallet_transaction.player_id → dim_player.player_id` ·
   `fact_bonus_transaction.player_id → dim_player.player_id` · `dim_player_vip_tier_scd.player_id → dim_player.player_id` ·
   `fact_bet.placed_date → dim_date.date_day` · `fact_wallet_transaction.transaction_date → dim_date.date_day` ·
   `fact_bonus_transaction.campaign_id → dim_campaign.campaign_id`.
3. **New measure** for each block in `measures.dax`, on the table named in its section header.
