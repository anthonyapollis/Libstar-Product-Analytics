# Libstar Product Analytics — Azure lakehouse completed project

End-to-end pipeline: **5 million deliberately dirty product records → Azure
Data Factory cleaning → Synapse serverless SQL → Qlik Sense, ML, ebook and
Excel reporting** — designed to run a full demo on an Azure free-trial credit.

> Synthetic data built on Libstar's public brand/category model
> (libstar.co.za). Not affiliated with Libstar Holdings.

## Why this exists

Consumer packaged goods companies run on catalog data that arrives messy —
inconsistent price formats, mixed units, mistyped brand names, legacy
category codes from prior org structures. Bad catalog data has a direct
business cost: mispriced SKUs erode margin, duplicate listings distort
demand forecasts, and unresolved brand names break rollup reporting used
for pricing and range decisions. This project demonstrates a governed fix:
a reproducible pipeline that catches and quantifies the mess (every
rejected row carries an explicit reason, not a silent drop), reconciles
one set of numbers across BI, ML and narrative reporting, and costs cents
per run to operate.

## Tech stack

| Layer | Tools |
|---|---|
| Data generation | Python (pandas, numpy) — seeded synthetic catalog |
| Storage | Azure Data Lake Storage Gen2 (raw / curated zones) |
| Transformation | Azure Data Factory mapping data flows |
| Query / serving | Azure Synapse Analytics (serverless SQL pools) |
| ML | scikit-learn (HistGradientBoostingRegressor, IsolationForest, KMeans) |
| BI | Qlik Sense (Qlik Cloud), Qlik Tabular Reporting |
| Reporting | openpyxl (Excel), python-docx (ebook), matplotlib (charts, SA map) |
| Ops | Azure CLI, PowerShell, Azure Cost Management budgets |

## Architecture

```
generate_dirty_products.py (5.1M rows, seeded mess)
        │  gzip CSV
        ▼
ADLS Gen2  raw/  ──────────────► reference/ (brand map + dims)
        │
        ▼
Azure Data Factory  pl_clean_products (mapping data flow, 8 vCores ≈ 6 min)
  · price/date/boolean/unit normalisation      · brand lookup fixes
  · legacy category resolution                   misspelled/junk brands
  · dedupe by product_id (latest wins)         · quarantine + reject_reason
        │  snappy parquet
        ▼
ADLS Gen2  curated/products_clean + products_quarantine + ml_anomalies
        │
        ▼
Synapse serverless (db libstar, schema rpt) — views, no idle cost
        │
        ├──► Qlik Sense Cloud (qlik/ — load script, dashboard spec,
        │      Tabular Reporting / NPrinting distribution)
        ├──► ml/train_models.py (price model, IsolationForest, KMeans)
        ├──► ebook/Libstar_Data_Story.docx (charts + SA map + narrative)
        └──► excel/Libstar_Product_Report.xlsx (formula-driven KPIs)
```

All reports read one aggregate layer (`data/aggregates/`, mirrored by the
`rpt.vw_*` views), so numbers reconcile across deliverables by construction.

## Repo map

| Path | What |
|---|---|
| `scripts/` | data generator, dims builder, charts, Excel/ebook builders, cost check |
| `adf/` | linked service, datasets, mapping data flow, pipeline + deploy script |
| `synapse/` | serverless DDL (views, credential, qlik_reader) + deploy script |
| `qlik/` | load script, dashboard spec, NPrinting/Tabular Reporting guide |
| `ml/` | training script + outputs (metrics, anomalies, segments) |
| `data/` | raw (LFS), reference dims, curated parquet (LFS), aggregates |
| `ebook/`, `excel/` | final deliverables |

## Data availability

Both ends of the pipeline are committed to this repo via **Git LFS**, not
just the polished output — so the numbers in the ebook/Excel/Qlik app can
be traced back to source:

- `data/raw/products_part_*.csv.gz` — the 5.1M-row raw synthetic catalog
  (before cleaning), ~230 MB
- `data/curated/products_clean/*.parquet` and `products_quarantine/*.parquet`
  — the Data Factory output: 4,284,971 clean products + 729,438 quarantined
  rows with reject reasons, ~190 MB
- `data/reference/*.csv` — the brand/category/province dimension tables the
  cleaning pipeline resolves against
- `data/aggregates/*.csv` — the exact rollups every report (Excel, ebook,
  Qlik reconciliation) reads

`data/local/*.csv` (flat CSV re-exports for offline Qlik Desktop use) is
**not** committed — it's fully derivable from the parquet above:

```powershell
git clone <this-repo>
git lfs install
git lfs pull
python scripts/export_local_extracts.py
```

## Cost teardown

Nothing in this design runs while idle — ADF bills per pipeline run,
Synapse serverless bills per query scanned, storage is the only standing
cost (~$0.03/month for ~1 GB). Kill switch, one command:

```powershell
az group delete --name rg-pargoparcels --yes
```

Safe to run once the Qlik app has completed its reload (it keeps working
after teardown — data loads into the app itself, not a live connection)
and everything else in this repo (ebook, Excel, `.qvf` export, local CSV
extracts) is generated and committed, since none of it depends on the
Azure resources staying up.

## Azure resources (rg-pargoparcels, South Africa North)

- `stpargoparcels01` — ADLS Gen2 (raw / curated / synapsefs)
- `adf-pargoparcels-za` — Data Factory
- `syn-pargoparcels` — Synapse workspace (serverless only);
  SQL endpoint `syn-pargoparcels-ondemand.sql.azuresynapse.net`, db `libstar`
- `pargo-trial-budget` — $200 budget, email alerts at 50/75/90% actual +
  100% forecast

## Cost profile (free-trial safe)

| Item | Cost |
|---|---|
| ADF data-flow run (8 vCores, ~6 min) | ≈ $0.50–0.80 per run |
| Synapse serverless | $5/TB scanned → < $0.001 per query here |
| Storage (~1 GB) | ≈ $0.02/month |
| Idle | $0 — nothing always-on |

Check spend: `scripts/check_costs.ps1` (Cost Management API throttles hard on
trial subscriptions — budget emails are the reliable guardrail).

## Rebuild from scratch

```powershell
python scripts/build_reference_dims.py
python scripts/build_brand_map.py
python scripts/generate_dirty_products.py          # ~15 min
# upload raw + reference to ADLS, then:
adf\deploy_adf.ps1
az datafactory pipeline create-run -g rg-pargoparcels --factory-name adf-pargoparcels-za --pipeline-name pl_clean_products
synapse\deploy_synapse.ps1
# download curated locally, then:
python ml/train_models.py
python scripts/make_charts.py
python scripts/build_excel_report.py
python scripts/build_ebook.py
```
