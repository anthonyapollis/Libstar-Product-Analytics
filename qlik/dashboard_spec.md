# Libstar Product Analytics — Qlik Sense dashboard spec

App name: **Libstar Product Analytics** · Data: `libstar_load_script.qvs`

Live app id `ce620f1c-5ad7-4add-801f-20ce0c044326` on
`go10njvx344b4j2.eu.qlikcloud.com`. **Fastest way to (re)build it:**

```powershell
.\qlik\build_qlik_app.ps1 -AppId ce620f1c-5ad7-4add-801f-20ce0c044326           # measures + visual layer
.\qlik\build_qlik_app.ps1 -AppId <id> -UploadData                              # full build incl. data upload + reload
.\qlik\build_qlik_app.ps1 -AppId <id> -VerifyOnly                              # health check
```

Reads `qlik\objects\measures.json` (9 master measures) and
`qlik\objects\app_objects_combined.json` (5 sheets, 28 child objects + the SA
province map) — the exact payload live in the tenant right now. Design system:
forest green `#1B4332` / terracotta `#BC6C25` / mustard `#E9C46A` / burgundy
`#780000` (deliberately distinct from the sibling Kalahari Petroleum project's
navy/steel-blue theme — different company, different identity). Every chart
carries a subtitle (what it shows) and footnote (its Synapse source view).
Sheet 3 has a real Qlik area map on `province` (Gauteng, Western Cape, etc. —
real SA province names resolve via Qlik's location service) in addition to
the bar-chart breakdowns originally specced below.

## Master measures

| Name | Definition | Format |
|---|---|---|
| Revenue 12m | `Sum(revenue_12m_zar)` | R# ##0;-R# ##0 |
| Avg Margin % | `Avg(margin_pct)` | 0.0% (already in %, use `Avg(margin_pct)/100` if formatting as %) |
| Total SKUs | `Count(distinct product_id)` | # ##0 |
| Active SKUs | `Count({<is_active={1}>} distinct product_id)` | # ##0 |
| Avg Rating | `Avg(rating)` | 0.00 |
| Stock Units | `Sum(stock_qty)` | # ##0 |
| Revenue per SKU | `Sum(revenue_12m_zar)/Count(distinct product_id)` | R# ##0 |
| Quarantined Rows | `Sum(row_count)` (DataQuality table) | # ##0 |

## Sheet 1 — Executive Overview
- KPI row: Revenue 12m · Avg Margin % · Total SKUs · Active SKUs · Avg Rating
- Donut: Revenue 12m by `product_group` (Perishable vs Ambient)
- Bar (top 10): Revenue 12m by `brand`, colored by `brand_solution`
- Line: Revenue 12m by `month_added` (catalog growth over time)
- Filter pane: product_group, category, brand_solution, province, year_added

## Sheet 2 — Category & Brand
- Treemap: `category` sized by Revenue 12m, colored by Avg Margin %
- Bar: Avg Margin % by `category` (sorted, reference line at overall avg)
- Stacked bar: Revenue by `category` split by `brand_solution`
- Pivot: brand × category — Revenue, Margin %, SKU count, Avg Rating

## Sheet 3 — Regional & Channel (SA map)
- **Map**: area layer on `province` (Qlik's default location service resolves
  South African province names; set Location scope → South Africa).
  Color by Revenue 12m, popup shows SKUs + margin.
- Bar: Revenue by `sales_channel`
- Combo: SKU count (bars) + Avg Margin % (line) by `province`

## Sheet 4 — Data Quality (the ADF story)
- KPI: Quarantined Rows · DQ pass rate `=1 - Sum(row_count)/(Count(distinct product_id)+Sum(row_count))`
- Bar: `reject_reason` by row_count (bad_price / bad_date / unknown_brand / …)
- Table: KpiSummary reconciliation vs Excel report (same Synapse views)
- Text panel: pipeline description (raw gzip CSV → ADF data flow → parquet)

## Sheet 5 — ML Insights
- Table: price anomalies (from `rpt.vw_ml_anomalies` once ML outputs are
  uploaded): product, brand, price vs category median, anomaly score
- Scatter: price_zar vs margin_pct colored by segment (sampled)
- KPI: price-model R² and MAE (from ml/outputs/metrics.json — shown as text)
