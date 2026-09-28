# Power BI — JSB reporting model and report

A finished Power BI project: semantic model (7 tables, 7 relationships, 10 DAX measures)
and a two-page report, loading from the CSVs in `data/`, with no database connection needed.

## Open it
1. Copy this whole `powerbi/` folder to your machine (e.g. `C:\JSB\powerbi\`).
2. In Power BI Desktop: **File → Open → `JSB_Assessment.pbip`**.
   (Older Desktop versions: first enable *Options → Preview features → Power BI Project (.pbip) save option*.)
3. If you put the folder anywhere other than `C:\JSB\powerbi\`: **Transform data → Edit parameters →
   DataFolder**, set it to your `data\` folder path **with a trailing backslash**, then **Apply**.
4. **Refresh**. Check the visuals against `expected_values.md`.

## What's in it
| File | What it is |
|---|---|
| `JSB_Assessment.pbip` | The project file you open |
| `JSB_Assessment.SemanticModel/model.bim` | Tables, Power Query (CSV import), relationships, DAX measures |
| `JSB_Assessment.Report/report.json` | Page 1 *NGR overview*: GGR, bonus cost, NGR, bonus liability cards; GGR vs NGR by product; bonus cost % of NGR by campaign. Page 2 *Player balances*: date slicer, deposits, balance per player from the ledger |
| `data/*.csv` | The dbt mart data (`dbt_jsb_assessment/models/marts/`) |
| `model.png` | The star schema |
| `measures.dax` | Every measure, readable |
| `expected_values.md` | What each visual should show, computed independently with pandas |
| `build_pbip.py` | Generates all of the above from one set of definitions and validates it |

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
- **Measures follow the SQL definitions** in `exercise3-schema-design/example_queries.sql`:
  - NGR = GGR − bonus money staked on lost bets (query a).
  - Campaign bonus cost is recognised when a grant resolves, and divided by total NGR (query b).
  - Balance as of a date is the sum of the ledger up to that date (query c).

## How it was verified, and the limit of that
No Power BI Desktop runs in this Linux build environment, so the project has **not** been opened in
Power BI here. What was checked:
- `build_pbip.py` validates that every visual field and measure reference resolves to the model,
  that every relationship column exists, and that there are no ambiguous filter paths. A negative
  test confirmed it catches an ambiguous relationship and a misspelled measure or column.
- `expected_values.md` is computed from the CSVs in pandas, independently of the DAX. It matches
  the MySQL and MariaDB query results and the dbt marts: NGR −90.00, sportsbook −160.00,
  bonus cost −27.78% of NGR, and player 1's balance of 1,160.00 on 2026-09-06.
- The report format mirrors the layout in the supplied `Demo.pbix`: Power BI Desktop 2.130,
  CY24SU06 theme.

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
