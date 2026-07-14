"""Build index.html — the Libstar interactive data story.

Self-contained single file: charts embedded as base64, an interactive SVG
choropleth of SA provinces (hover tooltips + live side panel) generated from
the same GeoJSON as the ebook map, and every number/table read from
data/aggregates + ml/outputs at build time so the page reconciles with the
Qlik app, Excel report and ebook by construction.
"""

import base64
import json
import os

import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..")
AGG = os.path.join(BASE, "data", "aggregates")
ML = os.path.join(BASE, "ml", "outputs")
CHARTS = os.path.join(BASE, "ebook", "charts")
OUT = os.path.join(BASE, "index.html")

NAVY, TEAL, GOLD, CORAL = "#8e1e4d", "#0fb5ae", "#ffb703", "#f3722c"


def img64(name):
    with open(os.path.join(CHARTS, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def rbn(x):
    return f"R{x/1e9:,.1f}bn"


def lerp_color(t):
    """light -> teal -> deep raspberry ramp for the choropleth"""
    stops = [(0xE3, 0xF8, 0xF6), (0x0F, 0xB5, 0xAE), (0x8E, 0x1E, 0x4D)]
    seg = min(int(t * 2), 1)
    f = t * 2 - seg
    a, b = stops[seg], stops[seg + 1]
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


def build_map(prov_df):
    with open(os.path.join(BASE, "data", "reference", "za_provinces.geojson"),
              encoding="utf-8") as f:
        gj = json.load(f)
    stats = prov_df.set_index("province")
    vmin, vmax = stats["revenue_12m_zar"].min(), stats["revenue_12m_zar"].max()

    def xy(lon, lat):
        return round((lon - 16.2) * 56, 1), round((-21.8 - lat) * -56 * -1, 1)

    paths = []
    for ft in gj["features"]:
        name = ft["properties"]["name"]
        row = stats.loc[name]
        t = (row["revenue_12m_zar"] - vmin) / (vmax - vmin)
        d = []
        geom = ft["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            ring = poly[0]
            # mainland only: drop the Prince Edward Islands (lat ~ -46) which
            # would quadruple the map bounds
            if ring[0][1] < -36 or ring[0][0] > 34:
                continue
            pts = [xy(lon, lat) for lon, lat in ring[::2]]  # thin points 2x
            d.append("M" + " ".join(f"{x},{y}" for x, y in pts) + "Z")
        paths.append(
            f'<path d="{" ".join(d)}" fill="{lerp_color(t)}" '
            f'data-name="{name}" data-rev="{rbn(row["revenue_12m_zar"])}" '
            f'data-skus="{int(row["sku_count"]):,}" '
            f'data-margin="{row["avg_margin_pct"]:.1f}%"/>')
    return "\n".join(paths)


def table(df, cols, fmts, cls=""):
    head = "".join(f"<th>{c[1]}</th>" for c in cols)
    rows = []
    for _, r in df.iterrows():
        tds = "".join(f"<td>{fmts.get(c[0], str)(r[c[0]])}</td>" for c in cols)
        rows.append(f"<tr>{tds}</tr>")
    return f'<table class="{cls}"><tr>{head}</tr>{"".join(rows)}</table>'


def main():
    kpi = pd.read_csv(os.path.join(AGG, "kpi_summary.csv")).iloc[0]
    cat = pd.read_csv(os.path.join(AGG, "category_performance.csv"))
    brand = pd.read_csv(os.path.join(AGG, "brand_performance.csv")).head(10)
    prov = pd.read_csv(os.path.join(AGG, "province_performance.csv"))
    chan = pd.read_csv(os.path.join(AGG, "channel_performance.csv"))
    dq = pd.read_csv(os.path.join(AGG, "data_quality.csv"))
    anom = pd.read_csv(os.path.join(ML, "price_anomalies.csv")).nsmallest(10, "anomaly_raw")
    metrics = json.load(open(os.path.join(ML, "metrics.json")))
    pm = metrics["price_model"]

    rev = kpi["revenue_12m_zar"]
    amb = cat[cat.product_group == "Ambient products"].revenue_12m_zar.sum()
    money = lambda v: f"R{v:,.0f}"
    pct = lambda v: f"{v:.1f}%"
    num = lambda v: f"{int(v):,}"

    cat_tbl = table(cat, [("category", "Category"), ("product_group", "Group"),
                          ("sku_count", "SKUs"), ("revenue_12m_zar", "Revenue 12m"),
                          ("avg_margin_pct", "Avg margin"), ("avg_price_zar", "Avg price")],
                    {"sku_count": num, "revenue_12m_zar": money,
                     "avg_margin_pct": pct, "avg_price_zar": lambda v: f"R{v:,.2f}"})
    brand_tbl = table(brand, [("brand", "Brand"), ("brand_solution", "Brand solution"),
                              ("sku_count", "SKUs"), ("revenue_12m_zar", "Revenue 12m"),
                              ("avg_margin_pct", "Avg margin")],
                      {"sku_count": num, "revenue_12m_zar": money, "avg_margin_pct": pct})
    dq_tbl = table(dq.assign(reject_reason=dq.reject_reason.str.rstrip(";").str.replace(";", " + ")),
                   [("reject_reason", "Reject reason"), ("row_count", "Rows")],
                   {"row_count": num})
    anom_tbl = table(anom, [("product_name", "Product"), ("category", "Category"),
                            ("brand", "Brand"), ("price_zar", "Price"),
                            ("cost_zar", "Cost"), ("margin_pct", "Margin"),
                            ("anomaly_raw", "Score")],
                     {"price_zar": lambda v: f"R{v:,.2f}", "cost_zar": lambda v: f"R{v:,.2f}",
                      "margin_pct": pct, "anomaly_raw": lambda v: f"{v:.4f}"})
    chan_rows = "".join(
        f'<div class="hbar"><span>{r.sales_channel}</span>'
        f'<div class="bar"><div style="width:{r.revenue_12m_zar/chan.revenue_12m_zar.max()*100:.1f}%"></div></div>'
        f'<b>{rbn(r.revenue_12m_zar)}</b></div>'
        for r in chan.itertuples())

    svg_paths = build_map(prov)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Libstar Product Analytics — From 5 Million Dirty Rows to One Trusted Catalog</title>
<style>
:root{{--navy:{NAVY};--navy2:#5c1433;--teal:{TEAL};--gold:{GOLD};--coral:{CORAL};
  --ink:#1f2430;--paper:#fdf6f9;--card:#fff}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,sans-serif;color:var(--ink);background:var(--paper);line-height:1.65}}
nav{{position:sticky;top:0;z-index:50;background:var(--navy2);display:flex;align-items:center;gap:16px;padding:12px 26px;flex-wrap:wrap}}
nav .brand{{color:var(--gold);font-weight:800;letter-spacing:.12em;font-size:.9rem}}
nav a{{color:#f6d9e6;text-decoration:none;font-size:.84rem}} nav a:hover{{color:#fff}}
nav .btn{{padding:6px 14px;border-radius:5px;font-weight:600;color:#fff}}
.b-teal{{background:var(--teal)}}.b-coral{{background:var(--coral)}}.b-navy{{background:#d6336c}}
nav .sp{{flex:1}}
header{{background:linear-gradient(165deg,var(--navy) 0%,#b3286b 55%,#8a5a00 100%);color:#fff;text-align:center;padding:70px 24px 60px}}
header h1{{font-size:2.7rem;margin-bottom:14px;line-height:1.2}}
header .sub{{max-width:880px;margin:0 auto 8px;font-size:1.12rem;color:#f6d9e6}}
.note{{max-width:920px;margin:28px auto 0;background:var(--gold);color:#4a2500;border-left:6px solid #c2410c;padding:16px 22px;text-align:left;border-radius:4px;font-size:.95rem}}
.kpis{{display:flex;flex-wrap:wrap;gap:16px;justify-content:center;max-width:1150px;margin:38px auto 0}}
.kpi{{background:var(--card);color:var(--ink);border-radius:10px;padding:20px 24px;min-width:200px;box-shadow:0 6px 18px rgba(0,0,0,.25);text-align:center}}
.kpi b{{display:block;font-size:1.75rem;color:var(--navy)}} .kpi span{{font-size:.84rem;color:#5a6474}}
section{{max-width:1100px;margin:0 auto;padding:58px 24px 6px}}
h2{{color:var(--navy);font-size:1.75rem;margin-bottom:8px;border-bottom:3px solid var(--teal);display:inline-block;padding-bottom:4px}}
h3{{color:var(--navy);margin:26px 0 6px;font-size:1.15rem}}
p{{margin:13px 0;max-width:72em}}
.dark{{background:var(--navy);color:#fbeaf1;max-width:none;padding:58px 0 44px;margin-top:52px}}
.dark .in{{max-width:1100px;margin:0 auto;padding:0 24px}}
.dark h2{{color:var(--gold);border-color:var(--gold)}} .dark p{{color:#f0c9dc}}
figure{{margin:24px 0;background:var(--card);border-radius:10px;padding:16px;box-shadow:0 3px 12px rgba(20,30,60,.08)}}
figure img{{width:100%;border-radius:4px}}
figcaption{{font-size:.85rem;color:#5a6474;margin-top:9px;font-style:italic}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:22px}} @media(max-width:840px){{.g2{{grid-template-columns:1fr}}}}
table{{border-collapse:collapse;width:100%;margin:16px 0;background:var(--card);font-size:.9rem;box-shadow:0 2px 8px rgba(20,30,60,.06)}}
th{{background:var(--navy);color:#fff;text-align:left;padding:9px 13px;white-space:nowrap}}
td{{padding:8px 13px;border-bottom:1px solid #f5e0ea}} tr:nth-child(even) td{{background:#fdf3f7}}
.dark table{{box-shadow:none}} .dark td{{color:#f6d9e6;border-color:#7a2050}} .dark tr:nth-child(even) td{{background:#6a173d}}
.callout{{background:#e3f8f6;border-left:6px solid var(--teal);padding:15px 20px;border-radius:4px;margin:20px 0}}
.callout.warn{{background:#fdece2;border-color:var(--coral)}}
code{{background:#eef1f6;padding:2px 6px;border-radius:4px;font-size:.88em}}
pre{{background:var(--navy2);color:#f6d9e6;padding:16px 20px;border-radius:8px;overflow-x:auto;font-size:.84rem;margin:16px 0}}
.mapwrap{{display:grid;grid-template-columns:2fr 1fr;gap:20px;align-items:start}}
@media(max-width:840px){{.mapwrap{{grid-template-columns:1fr}}}}
#zamap{{background:var(--card);border-radius:10px;box-shadow:0 3px 12px rgba(20,30,60,.08);padding:10px}}
#zamap path{{stroke:#fff;stroke-width:1.4;cursor:pointer;transition:opacity .15s}}
#zamap path:hover{{opacity:.75;stroke:var(--gold);stroke-width:2.5}}
#mapinfo{{background:var(--card);border-radius:10px;padding:20px;box-shadow:0 3px 12px rgba(20,30,60,.08);position:sticky;top:70px}}
#mapinfo b.pv{{font-size:1.3rem;color:var(--navy)}} #mapinfo .stat{{margin:10px 0;font-size:.95rem}}
#mapinfo .stat b{{color:var(--teal);font-size:1.25rem;display:block}}
.legend{{display:flex;align-items:center;gap:8px;font-size:.8rem;color:#5a6474;margin-top:8px}}
.legend .ramp{{flex:1;height:10px;border-radius:5px;background:linear-gradient(90deg,#e3f8f6,var(--teal),var(--navy))}}
.hbar{{display:grid;grid-template-columns:220px 1fr 110px;gap:12px;align-items:center;margin:9px 0;font-size:.92rem}}
.hbar .bar{{background:#f5e0ea;border-radius:5px;height:16px}} .hbar .bar div{{background:var(--teal);height:16px;border-radius:5px}}
.hbar b{{text-align:right;color:var(--navy)}}
footer{{background:var(--navy2);color:#c98aa8;text-align:center;padding:26px;font-size:.85rem;margin-top:56px}}
</style></head><body>

<nav><span class="brand">LIBSTAR PRODUCT ANALYTICS</span>
<a href="#story">Story</a><a href="#pipeline">Pipeline</a><a href="#shelf">Shelf</a>
<a href="#brands">Brands</a><a href="#map">Map</a><a href="#dq">Data quality</a>
<a href="#ml">ML</a><a href="#azure">Azure</a><a href="#build">How it's built</a>
<span class="sp"></span>
<a class="btn b-navy" href="https://github.com/anthonyapollis" target="_blank">GitHub repo</a>
<a class="btn b-teal" href="excel/Libstar_Product_Report.xlsx">Excel</a>
<a class="btn b-coral" href="ebook/Libstar_Data_Story.docx">Ebook</a></nav>

<header><h1>From 5 Million Dirty Rows<br>to One Trusted Catalog</h1>
<p class="sub">A consumer-packaged-goods data story — {int(kpi.raw_rows):,} catalog rows modelled on
Libstar's public brand portfolio, cleaned by Azure Data Factory, served by Synapse serverless SQL,
scored with machine learning, and reconciled to the rand across Qlik Sense, Excel and this page.</p>
<div class="note"><b>Case-study note:</b> Libstar is a real JSE-listed CPG group, but every record here is
synthetic — generated (seeded, reproducible) on Libstar's <i>public</i> brand/category model to
demonstrate the pipeline without using any private data. Not affiliated with Libstar Holdings.</div>
<div class="kpis">
<div class="kpi"><b data-n="5100000">0</b><span>raw rows generated (incl. planted duplicates)</span></div>
<div class="kpi"><b data-n="{int(kpi.total_skus)}">0</b><span>clean unique products after ADF</span></div>
<div class="kpi"><b data-n="{int(kpi.quarantined_rows)}">0</b><span>rows quarantined — each with a reason</span></div>
<div class="kpi"><b>R1.17tn</b><span>trailing 12-month revenue (synthetic)</span></div>
<div class="kpi"><b>{pm['r2']:.2f}</b><span>price-model R² · MAE R{pm['mae_zar']:.2f}</span></div>
</div></header>

<section id="story"><h2>1 · More than a product list</h2>
<p>CPG catalogs rot quietly. Prices arrive as <code>"R 1,234.56"</code> from one system and
<code>"ZAR1234"</code> from another; weights get captured in grams instead of kilograms; brands are
typed by hand; category codes from a previous org structure ("Groceries", "Snacks and confectionery")
linger years after a restructure. None of it looks urgent — until mispriced SKUs erode margin,
duplicate listings distort demand forecasts, and rollup reporting breaks exactly when a range review
needs it.</p>
<p>This project demonstrates the governed fix: a pipeline that <b>quantifies</b> the mess instead of
silently filtering it, resolves it with auditable rules, and publishes one set of numbers that every
downstream consumer — the live Qlik Sense app, the Excel pack, the ML models, this page — reconciles
to <b>exactly</b>.</p></section>

<section id="pipeline"><h2>2 · The pipeline: dirty in, trusted out</h2>
<pre>generate_dirty_products.py (5.1M rows, seeded mess)
        │  gzip CSV
        ▼
ADLS Gen2  raw/ ───────────► reference/ (brand map + dims)
        │
        ▼
Azure Data Factory · mapping data flow (8 vCores, ~6 min, ≈ R10/run)
  price/date/unit/boolean normalisation · brand lookup resolves misspelled
  brands AND legacy category names · dedupe (latest wins) · quarantine
        │  snappy parquet
        ▼
ADLS Gen2  curated/ ──► Synapse serverless SQL (rpt.* views, $0 idle)
        │
        ├──► Qlik Sense Cloud app (5 sheets, built via qlik-cli)
        ├──► scikit-learn (pricing · IsolationForest · KMeans)
        ├──► Excel report (formula-driven, reconciled)
        └──► Ebook + this data story</pre>
<figure><img src="{img64('06_data_quality.png')}" alt="Data quality funnel">
<figcaption>Figure 1 — {int(kpi.raw_rows):,} deduplicated rows in, {int(kpi.total_skus):,} unique clean
products out. Dates and prices are the biggest offenders.</figcaption></figure></section>

<section id="shelf"><h2>3 · What the shelf looks like</h2>
<p>Libstar's simplified operating model has two product groups. Ambient categories carry
<b>{amb/rev:.0%} of revenue</b> ({rbn(amb)} of {rbn(rev)}), led by Spreads, Meal ingredients and Wet
condiments; perishables — dairy, convenience meals, value-added meats, baby, fresh mushrooms — hold
the rest. Margins cluster tightly around the {kpi.avg_margin_pct:.0f}% portfolio average, so revenue
mix, not margin spread, is what moves the total.</p>
<div class="g2">
<figure><img src="{img64('01_revenue_by_category.png')}" alt="Revenue by category">
<figcaption>Figure 2 — Revenue by category, coloured by product group.</figcaption></figure>
<figure><img src="{img64('02_margin_by_category.png')}" alt="Margin by category">
<figcaption>Figure 3 — Margin by category vs the portfolio average.</figcaption></figure></div>
<h3>Category scorecard (full population)</h3>{cat_tbl}
<figure><img src="{img64('04_group_channel_mix.png')}" alt="Group and channel mix">
<figcaption>Figure 4 — Product-group split and the four routes to market.</figcaption></figure></section>

<section id="brands"><h2>4 · Brand power: three ways to win</h2>
<p>Three brand solutions compete on the same shelf: Libstar's own brands (Lancewood, Denny Mushrooms,
Cape Herb &amp; Spice…), Principal brands represented in South Africa (Bonne Maman, Kikkoman, Tabasco,
Maille), and private label for retailers. Principal brands price ~35% above comparable own-brand
products; private label sits ~20% below — yet "{brand.iloc[0].brand}" is the single biggest revenue
line ({rbn(brand.iloc[0].revenue_12m_zar)}) because it spans all twelve categories.</p>
<figure><img src="{img64('03_top_brands.png')}" alt="Top brands">
<figcaption>Figure 5 — Top 15 brands by revenue, coloured by brand solution.</figcaption></figure>
<h3>Top 10 brands</h3>{brand_tbl}</section>

<section id="map"><h2>5 · Where South Africa buys</h2>
<p>Hover (or tap) a province. Gauteng leads ({rbn(prov.set_index('province').loc['Gauteng','revenue_12m_zar'])}),
then Western Cape and KwaZulu-Natal — sales concentrate in the five provinces where the business has
production or distribution footprints.</p>
<div class="mapwrap">
<div id="zamap"><svg viewBox="0 0 960 760" xmlns="http://www.w3.org/2000/svg">{svg_paths}</svg>
<div class="legend"><span>{rbn(prov.revenue_12m_zar.min())}</span><div class="ramp"></div><span>{rbn(prov.revenue_12m_zar.max())}</span></div></div>
<div id="mapinfo"><b class="pv" id="mi-name">Hover a province</b>
<div class="stat">12-month revenue<b id="mi-rev">—</b></div>
<div class="stat">Products stocked<b id="mi-skus">—</b></div>
<div class="stat">Average margin<b id="mi-margin">—</b></div></div></div>
<h3>Routes to market</h3>{chan_rows}</section>

<section id="dq"><h2>6 · Data quality — where the numbers leak</h2>
<p>The Data Factory flow rejected <b>{int(kpi.quarantined_rows):,} rows
({kpi.quarantined_rows/kpi.raw_rows:.1%})</b> — and can say exactly why, row by row. Because reject
reasons ship into the same reporting layer as the clean data, data quality becomes a trend a team can
manage down, not an invisible loss.</p>{dq_tbl}
<div class="callout"><b>Reconciliation guarantee:</b> the Qlik app, the Excel report, the ebook and this
page all read the same aggregate layer. Revenue is <b>{money(rev)}</b> in all four — to the rand.</div></section>

<section id="ml"><h2>7 · Machine learning: pricing &amp; anomalies</h2>
<p><b>Pricing has learnable structure.</b> A gradient-boosted model predicts shelf price from category,
brand solution, channel, weight and rating with <b>R² = {pm['r2']:.2f}</b> and a mean absolute error
of <b>R{pm['mae_zar']:.2f}</b> on a mean price of R{pm['mean_price_zar']:.2f} — evidence that pricing
follows the portfolio's architecture, exactly what a well-governed catalog should show.</p>
<div class="g2">
<figure><img src="{img64('09_ml_anomalies.png')}" alt="Price anomalies">
<figcaption>Figure 6 — IsolationForest anomalies vs the normal price–margin cloud.</figcaption></figure>
<figure><img src="{img64('08_ml_segments.png')}" alt="Product segments">
<figcaption>Figure 7 — Four KMeans segments: volume movers, premium niche, two mainstream clusters.</figcaption></figure></div>
<div class="callout warn"><b>Why items get flagged, in plain language:</b> the model scored one million
products on price, cost, margin and weight <i>together</i>, and flagged the
{metrics['anomalies_flagged']:,} whose combination is most unlike the rest — a heavyweight item priced
like a small pack, an implausible margin, a luxury-priced commodity. These usually signal data-entry
or pricing errors, not genuine premium products. <b>Recommendation:</b> route this list to category
managers before the next price-list publication — correcting them before they reach shelves protects
margin and avoids customer-facing pricing errors.</div>
<h3>Top 10 to investigate first</h3>{anom_tbl}</section>

<div class="dark" id="azure"><div class="in"><h2>8 · Azure in production</h2>
<p>Everything runs on a free-trial credit by design — no always-on compute anywhere in the chain.</p>
<table><tr><th>Resource</th><th>Purpose</th><th>Idle cost</th></tr>
<tr><td><code>stpargoparcels01</code></td><td>ADLS Gen2 — raw / curated zones</td><td>≈ $0.03/month</td></tr>
<tr><td><code>adf-pargoparcels-za</code></td><td>Data Factory — cleaning data flow</td><td>$0 (per-run billing)</td></tr>
<tr><td><code>syn-pargoparcels</code></td><td>Synapse serverless SQL endpoint</td><td>$0 ($5/TB scanned)</td></tr>
<tr><td><code>pargo-trial-budget</code></td><td>$200 budget · email alerts at 50/75/90%</td><td>free</td></tr></table>
<p>Kill-switch once all consumers are loaded: <code>az group delete --name rg-pargoparcels --yes</code>.
The Qlik app (data loads in-app), the 36 MB .qvf export, the Excel pack, the ebook and this page all
keep working after teardown.</p></div></div>

<section id="build"><h2>9 · How it's built</h2>
<table><tr><th>Layer</th><th>Tools</th></tr>
<tr><td>Data generation</td><td>Python (pandas, numpy) — seeded synthetic catalog, reproducible mess</td></tr>
<tr><td>Storage</td><td>Azure Data Lake Storage Gen2 (raw / curated zones, Git LFS mirror in repo)</td></tr>
<tr><td>Transformation</td><td>Azure Data Factory mapping data flows</td></tr>
<tr><td>Serving</td><td>Azure Synapse Analytics serverless SQL</td></tr>
<tr><td>Machine learning</td><td>scikit-learn — HistGradientBoosting, IsolationForest, KMeans</td></tr>
<tr><td>BI</td><td>Qlik Sense Cloud — app, measures and 5 sheets built programmatically via qlik-cli</td></tr>
<tr><td>Reporting</td><td>openpyxl (Excel) · python-docx (ebook) · matplotlib (charts + SA map) · this page</td></tr>
<tr><td>Ops &amp; cost</td><td>Azure CLI, PowerShell, Cost Management budget alerts</td></tr></table>
<p>Rebuild from a clean clone:</p>
<pre>git lfs pull
python scripts/build_reference_dims.py &amp;&amp; python scripts/build_brand_map.py
python scripts/generate_dirty_products.py          # ~15 min
adf\\deploy_adf.ps1  →  run pl_clean_products  →  synapse\\deploy_synapse.ps1
python ml/train_models.py &amp;&amp; python scripts/make_charts.py
python scripts/build_excel_report.py &amp;&amp; python scripts/build_ebook.py
python scripts/build_data_story.py                 # this page</pre></section>

<footer>Libstar Product Analytics — synthetic portfolio project by Anthony Apollis · July 2026<br>
Data modelled on Libstar's public brand/category structure (libstar.co.za) · Not affiliated with Libstar Holdings</footer>

<script>
// interactive map
const info = {{name:document.getElementById('mi-name'),rev:document.getElementById('mi-rev'),
  skus:document.getElementById('mi-skus'),margin:document.getElementById('mi-margin')}};
document.querySelectorAll('#zamap path').forEach(p=>{{
  const show=()=>{{info.name.textContent=p.dataset.name;info.rev.textContent=p.dataset.rev;
    info.skus.textContent=p.dataset.skus;info.margin.textContent=p.dataset.margin;}};
  p.addEventListener('mouseenter',show);p.addEventListener('click',show);}});
// KPI counters: correct value shown immediately; count-up animation is a
// progressive enhancement (rAF is throttled in background/embedded tabs)
const fmt=n=>n.toLocaleString('en-ZA').replace(/,/g,' ');
document.querySelectorAll('.kpi b[data-n]').forEach(el=>{{
  const target=+el.dataset.n;
  el.textContent=fmt(target);
  if(document.visibilityState!=='visible')return;
  const t0=performance.now();
  const step=t=>{{const f=Math.min((t-t0)/1200,1);el.textContent=fmt(Math.round(target*f));
    if(f<1)requestAnimationFrame(step);else el.textContent=fmt(target);}};
  requestAnimationFrame(step);}});
</script>
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"written: {os.path.abspath(OUT)} ({os.path.getsize(OUT)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
