# Libstar product cleansing: SSIS generated from Biml

The Azure Data Factory mapping data flow [`adf/dataflow_df_clean_products.json`](../adf/dataflow_df_clean_products.json)
rebuilt as on-premises **SQL Server Integration Services** packages, generated from one
[Biml](Libstar.SSIS/Libstar_SSIS.biml) file. Same 5.1 million dirty product rows, same cleansing rules,
same published numbers: a different engine proving the same business result.

## Result: parity with the Azure Data Factory run

Run on SQL Server 2017 (Developer) through Visual Studio 2017 + SSDT. First verified 16 September 2026, then
re-verified on 17 September after the storage and memory fixes described below, with the same result.

| Measure | SSIS (this folder) | ADF ([`data/aggregates/kpi_summary.csv`](../data/aggregates/kpi_summary.csv)) |
|---|---:|---:|
| Clean SKUs published | **4,284,971** | 4,284,971 |
| Active SKUs | **2,142,870** | 2,142,870 |
| 12-month revenue (ZAR) | **1,170,282,306,878.76** | 1,170,282,306,878.77 |
| Average margin / price / rating | **35.00 / 71.68 / 3.00** | 35.0 / 71.68 / 3.0 |
| Stock units | **1,016,055,525** | 1,016,055,525 |
| Quarantined rows | **729,438** | 729,438 |

All 11 quarantine reasons match [`data_quality.csv`](../data/aggregates/data_quality.csv) row for row
(`bad_date;` 328,279 · `bad_price;` 230,750 · `unknown_brand;` 127,137 · … · `bad_price;bad_date;unknown_brand;unknown_category;` 36).
Revenue is a `float` sum over 4.3 M rows, so the last cent depends on the order rows are added (.77 on the first run,
.76 after the tables were compressed); every row-level value is identical.

**Finding.** The ADF summary labels 5,014,409 as `raw_rows`, but that is clean + quarantined. The files hold
**5,100,000** rows; the reconciliation gate accounts for the difference as **85,591 duplicate product rows**
removed by the latest-date-wins rule (`dw.vw_kpi_summary.duplicate_rows_removed`).

| Package | Rows read | Rows written | Rejected | 16 Sep | 17 Sep (after fixes) |
|---|---:|---:|---:|---:|---:|
| `LIB_00_LoadReference` | 23 | 23 | 0 | 10 s | 11 s |
| `LIB_01_StageRawProducts` | 5,100,000 | 5,100,000 | 0 | 25 min | 16 min |
| `LIB_02_CleanseProducts` | 5,100,000 | 4,370,562 valid | 729,438 quarantined | 28 min | 2 h 5 min |
| `LIB_03_PublishProducts` | 4,370,562 | 4,284,971 | 85,591 duplicates | 9.5 min | 4.5 min |

Run times are from the Visual Studio debugger on a 16 GB laptop running other applications, not a server. The slower
`LIB_02` on 17 September ran with 0.4–2 GB of free RAM and smaller buffers (see the incident log); it is a
memory-pressure number, not a regression in the package.

## What the packages do

```
data/raw/products_part_*.csv.gz  ──►  LIB_01  free-disk check → ForEach archive: Script Task gunzip → stage → delete the CSV
                                               → stg.products_raw (all text, + source_file, load_run_id)
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
  and an `OnError` event handler records `Failed` plus the error text. Every failure in the incident log below
  was diagnosed from that table.
- **Environment config.** Folder locations are not baked into packages. A non-empty package parameter wins;
  otherwise the package reads `etl.Config` and throws a clear message if it is missing.
- **Re-runnable.** Staging and output tables are truncated at the start of their step, so a rerun after any
  failure starts clean.

## Incident log: disk and memory limits

This ran on a development laptop with little free disk and RAM, which is exactly the kind of constraint a support
team inherits. Each row is a real failure from `etl.PackageRun`.

| Symptom | Root cause | Fix |
|---|---|---|
| `LIB_03` failed: *Could not allocate space for object 'SORT temporary run storage' in database 'tempdb'* | one `ROW_NUMBER()` over 4.4 M rows sorted the whole set in tempdb | publish in 8 hash buckets, each committed separately: about 1/8 of the sort space |
| `LIB_01` failed after 3.25 M rows: *Could not allocate a new page for database 'Libstar_SSIS' because of insufficient disk space* | all ten archives were expanded up front (776 MB) and the four big tables were uncompressed (~7.1 GB for a full reload) | **PAGE compression** on the four large tables; expand, stage and delete **one archive at a time**; a **free-disk check** fails the package in seconds, with a clear message, when the volume has less than `etl.Config MinFreeDiskMB` (default 1,500 MB) |
| `LIB_02` failed after 1.75 M rows: *Unspecified error … PrimeOutput method on SRC stg products_raw* | not a data error: the laptop had 0.6 GB of free RAM, and the debug log showed the SSIS buffer manager "low on virtual memory, unable to swap out buffers" 20 times. Cleansed rows are ~12 KB wide, so ~50 in-flight 10 MB buffers | `DefaultBufferSize` 3 MB on the cleansing data flow, which caps in-flight memory at about a third |
| `LIB_02` failed after 8.6 h: *Time-out occurred while waiting for buffer latch type 4* | with ~0.5 GB of free RAM Windows paged SQL Server's buffer pool out (the SQL error log reported it 12 times); a latch waited over 5 minutes for a page to come back from disk | no package change fixes this: the host needs memory. Rerun once ~1.5 GB was free; succeeded. On a real server, cap SQL Server `max server memory` and keep SSIS on its own host or memory budget |

Storage used by data and index pages, before and after compression:

| Table | Uncompressed | PAGE compressed |
|---|---:|---:|
| `stg.products_raw` | 2,859 MB | 690 MB |
| `stg.products_valid` | 1,618 MB | 680 MB |
| `dq.products_quarantine` | 272 MB | 145 MB |
| `dw.products_clean` | 2,337 MB | 865 MB |
| **Total for a full reload** | **~7.1 GB** | **~2.4 GB** |

Every failure above was diagnosed from the run log, the package's own error output and the SQL Server error log,
without opening the package designer.

**A fix that was rolled back.** Running the cleansing flow once per source archive also relieved memory, but each
iteration re-scanned the 5.1 M-row staging heap. With SQL Server squeezed to ~200 MB of buffer pool, it managed six
of ten archives in 90 minutes. That run was stopped and recorded as `Cancelled` in `etl.PackageRun` with the reason.
A single scan with smaller buffers was the better trade-off.

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
