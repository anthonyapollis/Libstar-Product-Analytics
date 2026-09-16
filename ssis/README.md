# Libstar product cleansing: SSIS generated from Biml

The Azure Data Factory mapping data flow [`adf/dataflow_df_clean_products.json`](../adf/dataflow_df_clean_products.json)
rebuilt as on-premises **SQL Server Integration Services** packages, generated from one
[Biml](Libstar.SSIS/Libstar_SSIS.biml) file. Same 5.1 million dirty product rows, same cleansing rules,
same published numbers: a different engine proving the same business result.

## Result: parity with the Azure Data Factory run

Run on SQL Server 2017 (Developer) through Visual Studio 2017 + SSDT, 16 September 2026.

| Measure | SSIS (this folder) | ADF ([`data/aggregates/kpi_summary.csv`](../data/aggregates/kpi_summary.csv)) |
|---|---:|---:|
| Clean SKUs published | **4,284,971** | 4,284,971 |
| Active SKUs | **2,142,870** | 2,142,870 |
| 12-month revenue (ZAR) | **1,170,282,306,878.77** | 1,170,282,306,878.77 |
| Average margin / price / rating | **35.00 / 71.68 / 3.00** | 35.0 / 71.68 / 3.0 |
| Stock units | **1,016,055,525** | 1,016,055,525 |
| Quarantined rows | **729,438** | 729,438 |

All 11 quarantine reasons match [`data_quality.csv`](../data/aggregates/data_quality.csv) row for row
(`bad_date;` 328,279 · `bad_price;` 230,750 · `unknown_brand;` 127,137 · … · `bad_price;bad_date;unknown_brand;unknown_category;` 36).

**Finding.** The ADF summary labels 5,014,409 as `raw_rows`, but that is clean + quarantined. The files hold
**5,100,000** rows; the reconciliation gate accounts for the difference as **85,591 duplicate product rows**
removed by the latest-date-wins rule (`dw.vw_kpi_summary.duplicate_rows_removed`).

| Package | Rows read | Rows written | Rejected | Run time |
|---|---:|---:|---:|---:|
| `LIB_00_LoadReference` | 23 | 23 | 0 | 10 s |
| `LIB_01_StageRawProducts` | 5,100,000 | 5,100,000 | 0 | 25 min |
| `LIB_02_CleanseProducts` | 5,100,000 | 4,370,562 valid | 729,438 quarantined | 28 min |
| `LIB_03_PublishProducts` | 4,370,562 | 4,284,971 | 85,591 duplicates | 9.5 min |

Run times are from the Visual Studio debugger on a laptop with 1 GB of free RAM; a server run is far faster.

## What the packages do

```
data/raw/products_part_*.csv.gz  ──►  LIB_01  Script Task gunzip → ForEach file loop → stg.products_raw (all text, + source_file, load_run_id)
data/reference/brand_map.csv     ──►  LIB_00  → ref.brand_map
                                       LIB_02  Derived Column: normalise text
                                               Derived Column: cast types (a failed cast becomes NULL, as ADF toDouble/toDate)
                                               Derived Column: value rules (grams → kg, negative stock → 0, rating 0–5, Y/N/1/0/TRUE…)
                                               Lookups on ref.province_map / channel_map / category_map / brand_map
                                               reject_reason → Conditional Split → stg.products_valid | dq.products_quarantine
                                       LIB_03  reconciliation gate (raw = valid + quarantine, else THROW) → dedupe → dw.products_clean
                                       LIB_Master runs 00 → 03, binding parameters to each child
```

The ADF `case()` chains became **rule tables** (`ref.*`): a support engineer adds a province abbreviation
with an `INSERT`, not a package redeploy.

## Built for support, not just for the demo

- **Run log.** Every package writes `etl.PackageRun` on start, closes it with rows read / written / rejected,
  and an `OnError` event handler records `Failed` plus the error text. Two real failures during development
  were diagnosed straight from that table (a missing data folder, and tempdb running out of disk).
- **Environment config.** Folder locations are not baked into packages. A non-empty package parameter wins;
  otherwise the package reads `etl.Config` and throws a clear message if it is missing.
- **Re-runnable.** Staging and output tables are truncated at the start of their step; decompression skips
  files that are already expanded.
- **Space-aware publish.** Deduplicating 4.4 M rows in one statement sorted the whole set in tempdb and filled
  the disk. The publish now works in 8 hash buckets, each committed on its own, so tempdb needs about 1/8 of
  the space and a rerun simply starts again.

## Run it

```powershell
sqlcmd -S localhost -E -i ssis\sql\00_setup_Libstar_SSIS.sql      # target database, rule tables, views
.\ssis\run_ssis.ps1 -Configure                                     # this machine's folders → etl.Config
```

1. Open `ssis\Libstar.SSIS.sln` in Visual Studio with SSDT and [BimlExpress](https://www.varigence.com/bimlexpress).
2. Right-click `Libstar_SSIS.biml` → **Generate SSIS Packages** (the database must exist; Biml reads table metadata).
3. Right-click `LIB_Master.dtsx` → **Execute Package**, or build and run `.\ssis\run_ssis.ps1` where the SQL Server
   Integration Services feature is installed.
4. `.\ssis\run_ssis.ps1 -ReconcileOnly` prints the run log, KPI summary and reject breakdown.

## Files

| Path | Purpose |
|---|---|
| `Libstar.SSIS/Libstar_SSIS.biml` | the single source of truth; all five packages are generated from it |
| `Libstar.SSIS/*.dtsx` | generated packages, committed so they can be reviewed without BimlExpress |
| `sql/00_setup_Libstar_SSIS.sql` | target schemas, rule tables, audit/config tables, reconciliation views |
| `run_ssis.ps1` | configure, run with DTExec, reconcile |
