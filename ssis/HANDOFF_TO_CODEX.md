# Handoff to Codex: SSIS + Biml work in progress

Author: Claude (2026-09-16). Branch: `ssis-biml-wip`. **Nothing here has been compiled or run yet.**

## Why this exists

Anthony is applying for **FPG – Managed Services Intermediate BI Developer**. The end client (a printer
brand) runs a ~20-year-old Microsoft estate: **SSIS + SQL Server + SSAS Tabular**, with ADF and Fabric
pipelines, and a planned migration to Fabric. His portfolio had no SSIS. The goal is to rebuild a few
existing portfolio ETL jobs as **Biml-generated SSIS packages** and push them to the matching repos.

Job spec: `C:\Users\Anthony.DESKTOP-ES5HL78\Downloads\Intermediate BI Developer - FPG.pdf`
Interview transcript: `C:\Users\Anthony.DESKTOP-ES5HL78\Downloads\Recording (15).txt`

## What is done (this folder)

| File | State |
|---|---|
| `sql/00_setup_Libstar_SSIS.sql` | **Run successfully** on local `localhost` (SQL Server 2017 Dev). Creates DB `Libstar_SSIS`: `etl.PackageRun`, `stg.products_raw`, `ref.{brand,province,channel,category}_map`, `stg.products_valid`, `dq.products_quarantine`, `dw.products_clean`, 2 views. |
| `Libstar.SSIS/BimlScripts/Libstar_SSIS.biml` | Written, **never compiled**. One file generates 5 packages (below). |
| `Libstar.SSIS/Libstar.SSIS.dtproj` + `Project.params` + `.database` | Hand-built from an existing VS2019 SSIS project template. ProductVersion 16.0.5467.0, `TargetServerVersion=SQLServer2017`, `DontSaveSensitive`, empty package list. Opens in **VS2019** (has SSIS ext + BimlExpress 5.0). |

Packages the Biml defines (port of ADF data flow `adf/dataflow_df_clean_products.json`):

1. `LIB_00_LoadReference` – `data/reference/brand_map.csv` → `ref.brand_map`
2. `LIB_01_StageRawProducts` – C# Script Task gunzips `data/raw/products_part_*.csv.gz` to a work folder, ForEach file loop → `stg.products_raw` (all text)
3. `LIB_02_CleanseProducts` – derived columns (normalise, cast with IgnoreFailure, value rules), 4 lookups on `ref.*`, reject_reason, conditional split → `stg.products_valid` / `dq.products_quarantine`
4. `LIB_03_PublishProducts` – reconciliation gate (raw = valid + quarantine, else THROW), ROW_NUMBER dedupe → `dw.products_clean`
5. `LIB_Master` – Execute Package tasks with parameter bindings

Every package: package parameters `ServerName, RawFolder, WorkFolder, ReferenceFolder`; run log start/end in
`etl.PackageRun`; OnError event handler writes `Failed` + error text.

## Acceptance target (parity with the ADF version)

From `data/aggregates/kpi_summary.csv` and `data_quality.csv`:
- raw rows **5,014,409**, clean **4,284,971**, quarantined **729,438**
- quarantine breakdown by `reject_reason` must match `data_quality.csv` row for row.

Check with `SELECT * FROM dw.vw_kpi_summary; SELECT * FROM dq.vw_reject_summary;`

## Blockers / known risks

- **Biml cannot be compiled headlessly here.** `BimlEngine.dll`'s MSBuild `BimlCompilerTask` demands a paid
  BimlStudio product key. Generation must be done in the VS2019 GUI: open `Libstar.SSIS.dtproj`, right-click
  `Libstar_SSIS.biml` → *Generate SSIS Packages*. The DB must exist first (Biml reads column metadata).
- Unverified Biml syntax guesses, most likely to need fixing on first compile:
  `LocaleId="Lcid1033"` on a DerivedColumns node; `ParameterBinding VariableName="User.X"`;
  `ExternalProjectPackage Package="X.dtsx"`; ScriptTaskProject structure; `ErrorRowDisposition` on derived columns.
- Machine locale is **en-ZA with `,` decimal separator** – string→DT_R8 casts may misparse `54.06`. That is why
  `LocaleId` 1033 is set on the cast component; verify.
- SSIS string functions are case-sensitive; the brand/category key logic mirrors ADF's `replace` before `lower` on purpose.
- Run via ispac: build in VS, then `DTExec /Project bin\Development\Libstar.SSIS.ispac /Package LIB_Master.dtsx /Par "$Package::RawFolder";"<repo>\data\raw" ...`
  (DTExec 140 at `C:\Program Files\Microsoft SQL Server\140\DTS\Binn\DTExec.exe`).

## Remaining plan (not started)

1. Compile, run, reach ADF parity for Libstar; add `ssis/README.md` + `run_ssis.ps1`; commit generated `.dtsx`.
2. **KalahariPetroleum_DW_Azure_Qlik** – metadata-driven Biml: source ERP DB `AngloData_QA_20220825_1820` (local)
   → new DB `KalahariDW_SSIS`. Dims = stage + MERGE (DimLocation, DimProduct, DimEquipment, DimCostCentre via
   attribute hash); facts = incremental high-watermark on source Id with surrogate-key lookups
   (FactFuelTransaction, FactFuelDelivery, FactMeterReading). Logic source: `sql/01_create_load_dw_full.sql`.
   Parity target = row counts of the existing `dw.*` tables in the source DB. Never write to `dbo` there.
3. **Lyra-Analytics-Project** – SCD Type 2 package for consent (`data/dimensions/DimConsent_SCD2_sample500.csv`):
   stage snapshot → lookup current row on (EmployeeNaturalKey, ConsentType) → hash compare → expire + insert.
   Needs a generated "day 2" snapshot with changes; prove re-running day 2 is a no-op.
4. Interview coverage extras: SSAS Tabular model (local `MSSQLServerOLAPService` is running) with DAX + dynamic RLS
   over the Kalahari star; a Fabric migration note (SSIS → Fabric pipelines/dataflows).
5. Thank-you email to FPG (interviewers mention hiring manager Danelle) pointing to the relevant repos.

Reference books on disk: `Downloads\The Data Warehouse Toolkit, 3rd Edition.pdf`,
`Downloads\vdoc.pub_star-schema-the-complete-reference.pdf`, `Downloads\Leonard-Bradshaw2020_Book_SQLServerDataAutomationThrough.pdf` (Biml frameworks),
`Downloads\ExpertSSIS.pdf`, `Downloads\Steve Hobberman Data Modeling Books\`.
