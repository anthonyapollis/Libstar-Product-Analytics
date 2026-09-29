# Power BI package: provenance (QA-11)

| Item | Value |
|---|---|
| Package | `JSB_PowerBI_v7.zip` (22 files, 88 KB) |
| SHA-256 | `c84026cfd6f7c37d633807e4cbfbc6a72412d046406722883090c2334cebdf8c` |
| Source commit | `1991bdee5d1d6be2d6e75a176519b2fa67845e24` (branch `claude/sleepy-hawking-uiq0u9`) |
| Built with | `git archive`, git 2.43.0 |
| Per-file hashes | [`powerbi_v7_files.sha256`](powerbi_v7_files.sha256) |

## What's in it, and only that
| Included | Why |
|---|---|
| `JSB_Assessment.pbip` | the file Power BI opens |
| `JSB_Assessment.SemanticModel/` (`model.bim`, `definition.pbism`, `.platform`) | the model, with all 11 tables' data embedded |
| `JSB_Assessment.Report/` (`report.json`, `definition.pbir`, `.platform`, theme) | the four pages |
| `data/` (11 CSVs) | the exported tables: exactly the 11 tables in the model, one file each |
| `expected_values.md` | the value checklist for every visual |
| `PACKAGE_README.md` | how to open it, what's inside, and the "is this current?" check |

**Left out on purpose:**
- the build and export scripts (`build_pbip.py`, `export_data.py`) and `__pycache__`;
- the diagrams (`model.mmd`, `model.png`) and `measures.dax` (the measures are inside `model.bim`);
- the two query marts that the report doesn't use (`mart_ngr_by_product_monthly.csv`, `mart_bonus_cost_pct_of_ngr.csv`);
- any older PBIP/PBIX, virtual environments and databases.

## Checks run on the unpacked package
- **Fresh data:** a fresh database load, then `dbt build --full-refresh` (78/78), then `export_data.py`, then `build_pbip.py`. That produced **no change** to any committed Power BI file, so the committed project is current.
- **Every JSON file parses**, and `definition.pbir` points at `../JSB_Assessment.SemanticModel`.
- **For all 11 tables, the data embedded in `model.bim` equals `data/<table>.csv` row for row.** That includes `ingest_runs` = 4 runs, starting with the ABANDONED run 1.
- **Values** (`expected_values.md`, computed independently in pandas): GGR 260.00, bonus cost 40.00, NGR 220.00, liability 10.00, Registration Bonus 40.00 = 18.18%, 4 runs.

## Reproduce
```bash
git archive --format=zip --prefix=JSB_PowerBI_v7/ -o JSB_PowerBI_v7.zip \
  1991bdee5d1d6be2d6e75a176519b2fa67845e24:candidate-assessment/powerbi \
  JSB_Assessment.pbip JSB_Assessment.SemanticModel JSB_Assessment.Report expected_values.md PACKAGE_README.md \
  data/dim_player.csv data/dim_player_vip_tier_scd.csv data/dim_campaign.csv data/dim_date.csv \
  data/fact_bet.csv data/fact_wallet_transaction.csv data/fact_bonus_transaction.csv \
  data/fct_recon_exceptions.csv data/mart_recon_bridge.csv data/ingest_runs.csv data/transactions.csv
```
(Run it from the repository root.) With a different git version, check the unpacked files with
`sha256sum -c powerbi_v7_files.sha256` instead.

## Rejected evidence (kept for the record, never used in the submission)
`rejected/stale_powerbi_page1_ngr_overview.png` and `rejected/stale_powerbi_page4_ingestion.png` are the
user's 2026-09-29 Power BI Desktop captures. They show an **old** copy: GGR −70.00, NGR −90.00,
liability 50.00, −27.78%, and 3 runs with run 1 still "RUNNING". "Last saved: Yesterday at 21:21"
confirms it's an earlier project folder. They are not P4 evidence.

| File | SHA-256 |
|---|---|
| `rejected/stale_powerbi_page1_ngr_overview.png` | `511bfdb133ebfac7ce9ce355685b0b1c1ca6f9e37f5c8738a211097b9f273d98` |
| `rejected/stale_powerbi_page4_ingestion.png` | `cebdc3d70201d7aba524084d842e6a1b5efd510dfabca2aa7cac116eba0b79b7` |
