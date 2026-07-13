# Qlik Sense (Qlik Cloud) setup — Libstar Product Analytics

Tenant: `https://go10njvx344b4j2.eu.qlikcloud.com`

## 1. Open the Synapse firewall for Qlik Cloud

The Synapse workspace currently allows Azure services and your home IP only.
Qlik Cloud EU connects from Qlik's published egress IPs. Either add those
ranges (see Qlik help: "Allowlisting domain names and IP addresses",
eu.qlikcloud.com region) with:

```powershell
az synapse workspace firewall-rule create --name QlikCloudEU-1 `
  --workspace-name syn-pargoparcels --resource-group rg-pargoparcels `
  --start-ip-address <first-ip> --end-ip-address <last-ip>
```

or, for a quick demo only, allow all IPs (remove afterwards):

```powershell
az synapse workspace firewall-rule create --name TempAllowAll `
  --workspace-name syn-pargoparcels --resource-group rg-pargoparcels `
  --start-ip-address 0.0.0.0 --end-ip-address 255.255.255.255
```

## 2. Create the data connection

In the tenant: **Data Integration / Analytics > Create > Data connection >
Microsoft Azure Synapse Analytics** (ODBC):

| Setting  | Value |
|---|---|
| Host     | `syn-pargoparcels-ondemand.sql.azuresynapse.net` |
| Port     | 1433 |
| Database | `libstar` |
| User     | `qlik_reader` |
| Password | in `.secrets/qlik_reader.txt` (local repo, not committed) |
| Name     | `Azure_Synapse_Libstar` |

## 3. Create the app

1. New analytics app: **Libstar Product Analytics**.
2. Data load editor -> paste `libstar_load_script.qvs` -> **Load data**.
3. Build sheets per `dashboard_spec.md` (master measures are listed at the
   bottom of the load script).

## Costs

Synapse serverless bills ~$5 per TB scanned. The curated parquet is well
under 1 GB, so each full Qlik reload costs a fraction of a cent. Schedule
reloads daily at most; there is no always-on compute in this design.
