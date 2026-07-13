# Handoff: build the Qlik Cloud app (Libstar Product Analytics)

Audience: an agent with browser access to the Qlik Cloud tenant and shell
access to this machine. Everything referenced is inside this repo
(`PargoParcels/`). Do not paste secret values into chat, commits or logs —
reference the files.

## Context

- Tenant: `https://go10njvx344b4j2.eu.qlikcloud.com` (EU). User is tenant admin.
- Data source: Azure Synapse **serverless** SQL
  - Server: `syn-pargoparcels-ondemand.sql.azuresynapse.net`, port 1433
  - Database: `libstar`, schema `rpt` (views: vw_products, vw_data_quality,
    vw_ml_anomalies, vw_kpi_summary, vw_category_performance, …)
  - SQL login: `qlik_reader`, password in `.secrets/qlik_reader.txt`
- Azure CLI is logged in (subscription `cea67e6f-...`); resource group
  `rg-pargoparcels`.

## Steps

### 1. Open the Synapse firewall for Qlik Cloud (temporary)

```powershell
az synapse workspace firewall-rule create --name TempAllowAll `
  --workspace-name syn-pargoparcels --resource-group rg-pargoparcels `
  --start-ip-address 0.0.0.0 --end-ip-address 255.255.255.255
```

(Qlik Cloud EU egress IPs are not allowlisted; this temp rule is removed in
step 7.)

### 2. Create the data connection

Tenant > Analytics > Create > Data connection > **Azure Synapse Analytics**:
host/port/db/user as above, password from `.secrets/qlik_reader.txt`.
Name it exactly **`Azure_Synapse_Libstar`** (the load script references this
name via `LIB CONNECT TO`).

### 3. Create the app

New analytics app named **Libstar Product Analytics** (any shared space is
fine). Open **Data load editor**, replace the script with the full contents
of `qlik/libstar_load_script.qvs`, save.

### 4. Load data

Run **Load data**. Expect ~4.28M rows into `Products` plus small tables
(DataQuality 11 rows, MlAnomalies 2,000, KpiSummary 1). Takes a few minutes.
If connection fails: verify step 1 rule exists and the connection name
matches.

### 5. Build sheets

Follow `qlik/dashboard_spec.md` exactly — it lists the 5 sheets
(Executive Overview, Category & Brand, Regional & Channel with SA map,
Data Quality, ML Insights) and the master-measure definitions (create
those first). For the map sheet: area layer on `province`, location scope
South Africa.

### 6. Reconcile (must match, from Synapse rpt.vw_kpi_summary)

| Measure | Expected |
|---|---|
| Total SKUs | 4 284 971 |
| Revenue 12m | R1 170 282 306 878.76 |
| Avg margin % | 35.00 |
| Avg price | R71.68 |
| Active SKUs | 2 142 870 |
| Quarantined rows (DataQuality sum) | 729 438 |

These same numbers are in `excel/Libstar_Product_Report.xlsx` (KPI_Summary)
and the ebook.

### 7. Clean up + local artifact

1. Export the app: app context menu > Export (with data) → save as
   `qlik/Libstar_Product_Analytics.qvf` in this repo (project must be local).
2. Remove the temp firewall rule:

```powershell
az synapse workspace firewall-rule delete --name TempAllowAll `
  --workspace-name syn-pargoparcels --resource-group rg-pargoparcels --yes
```

3. Tell Anthony the app is live — he then wants the Azure resource group
   deleted to stop all costs (`az group delete -n rg-pargoparcels --yes`),
   but ONLY after confirming the reload succeeded and the .qvf export is in
   the repo. After teardown, the app keeps working (data is loaded into the
   app), and local mode covers everything else
   (`qlik/libstar_load_script_local.qvs` + `data/local/`).

## Optional (nice to have)

- Tabular Reporting: bind `excel/Libstar_Product_Report.xlsx` named tables
  as a report template per `qlik/nprinting_tabular_reporting.md` and create
  a weekly report task.
