define([
  "qlik", "jquery", "./properties",
  "text!./libstar-command-intelligence.css",
  "text!./data/kpi_summary.csv",
  "text!./data/category_performance.csv",
  "text!./data/brand_performance.csv",
  "text!./data/channel_performance.csv",
  "text!./data/province_performance.csv",
  "text!./data/catalog_growth.csv",
  "text!./data/data_quality.csv",
  "text!./data/metrics.json",
  "text!./data/price_anomalies.csv",
  "text!./data/segments_summary.csv"
], function (qlik, $, properties, cssText, kpiText, categoryText, brandText, channelText, provinceText, growthText, qualityText, metricsText, anomalyText, segmentText) {
  "use strict";

  if (!document.getElementById("libstar-command-intelligence-css")) {
    var style = document.createElement("style");
    style.id = "libstar-command-intelligence-css";
    style.textContent = cssText;
    document.head.appendChild(style);
  }

  function csv(text) {
    var rows = [], row = [], field = "", quoted = false;
    for (var i = 0; i < text.length; i += 1) {
      var ch = text[i], next = text[i + 1];
      if (ch === '"' && quoted && next === '"') { field += '"'; i += 1; }
      else if (ch === '"') quoted = !quoted;
      else if (ch === "," && !quoted) { row.push(field); field = ""; }
      else if ((ch === "\n" || ch === "\r") && !quoted) {
        if (ch === "\r" && next === "\n") i += 1;
        row.push(field); field = "";
        if (row.some(function (v) { return v !== ""; })) rows.push(row);
        row = [];
      } else field += ch;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    var headers = rows.shift() || [];
    return rows.map(function (values) {
      var out = {};
      headers.forEach(function (key, index) { out[key] = values[index] || ""; });
      return out;
    });
  }

  function n(value) { var parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; }
  function esc(value) { return String(value == null ? "" : value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function money(value, short) {
    value = n(value);
    if (short) {
      if (value >= 1e12) return "R" + (value / 1e12).toFixed(2) + "tn";
      if (value >= 1e9) return "R" + (value / 1e9).toFixed(1) + "bn";
      if (value >= 1e6) return "R" + (value / 1e6).toFixed(1) + "m";
    }
    return "R " + Math.round(value).toLocaleString("en-ZA");
  }
  function count(value) {
    value = n(value);
    if (value >= 1e9) return (value / 1e9).toFixed(2) + "bn";
    if (value >= 1e6) return (value / 1e6).toFixed(2) + "m";
    if (value >= 1e3) return (value / 1e3).toFixed(1) + "k";
    return Math.round(value).toLocaleString("en-ZA");
  }
  function pct(value, digits) { return n(value).toFixed(digits == null ? 1 : digits) + "%"; }
  function max(rows, field) { return Math.max.apply(Math, rows.map(function (r) { return n(r[field]); }).concat([1])); }
  function sum(rows, field) { return rows.reduce(function (total, row) { return total + n(row[field]); }, 0); }

  var kpi = csv(kpiText)[0];
  var categories = csv(categoryText);
  var brands = csv(brandText);
  var channels = csv(channelText);
  var provinces = csv(provinceText);
  var growth = csv(growthText);
  var quality = csv(qualityText);
  var metrics = JSON.parse(metricsText);
  var anomalies = csv(anomalyText);
  var segments = csv(segmentText);

  var sheetMap = {
    exec: "sheet-exec", portfolio: "sheet-catbrand", network: "sheet-regional",
    quality: "sheet-dq", ml: "sheet-ml", explorer: "sheet-product-lab"
  };
  var pageNames = {
    exec: "Executive Command Centre", portfolio: "Category & Brand Portfolio",
    network: "Channel & Regional Network", quality: "Data Quality Control",
    ml: "ML Decision Lab", explorer: "Product Exception Explorer"
  };

  var icons = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    box: '<path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="m4 7 8 4 8-4v10l-8 4-8-4V7Z"/><path d="M12 11v10"/>',
    factory: '<path d="M3 21V9l6 3V8l6 3V4h6v17H3Z"/><path d="M7 17h2M13 17h2M18 8h3"/>',
    route: '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h4a3 3 0 0 1 3 3v6a3 3 0 0 0 3 3"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.4 8 8 9 4.6-1 8-4 8-9V6l-8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
    spark: '<path d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    trend: '<path d="M3 18 9 12l4 4 8-10"/><path d="M16 6h5v5"/>',
    map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/>',
    alert: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17h.01"/>'
  };
  function icon(name) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || icons.grid) + '</svg>'; }

  function nav(active) {
    var items = [
      ["exec", "grid", "Overview"], ["portfolio", "box", "Portfolio"], ["network", "route", "Network"],
      ["quality", "shield", "Quality"], ["ml", "spark", "ML Lab"], ["explorer", "search", "Explorer"]
    ];
    return '<aside class="lci-nav"><div class="lci-monogram">L<span>+</span></div><div class="lci-navrule"></div>' + items.map(function (item) {
      return '<button class="lci-navitem' + (active === item[0] ? ' active' : '') + '" data-page="' + item[0] + '">' + icon(item[1]) + '<span>' + item[2] + '</span></button>';
    }).join("") + '<div class="lci-navfoot"><span>PORTFOLIO<br>CASE STUDY</span></div></aside>';
  }

  function header(page, eyebrow, summary) {
    return '<header class="lci-header"><div class="lci-title"><span class="lci-eyebrow">' + esc(eyebrow) + '</span><h1>SHELFLINE <b>RETAIL + MANUFACTURING</b> INTELLIGENCE</h1><p>' + esc(summary) + '</p></div><div class="lci-asof"><i></i><span>MODEL SNAPSHOT<br><b>30 JUN 2026</b></span></div></header><div class="lci-pagebar"><span>' + esc(pageNames[page]) + '</span><div><b>SYNTHETIC CASE STUDY</b><em>Executive decision system</em></div></div>';
  }

  function card(title, subtitle, body, cls) {
    return '<section class="lci-card ' + (cls || "") + '"><div class="lci-cardhead"><div><h2>' + esc(title) + '</h2><p>' + esc(subtitle) + '</p></div></div>' + body + '</section>';
  }
  function metric(iconName, tone, label, value, note) {
    return '<article class="lci-kpi"><span class="lci-kpiicon ' + tone + '">' + icon(iconName) + '</span><div><small>' + esc(label) + '</small><strong>' + esc(value) + '</strong><p>' + esc(note) + '</p></div></article>';
  }
  function bars(rows, labelField, valueField, valueFormat, colorClass, limit) {
    rows = rows.slice().sort(function (a, b) { return n(b[valueField]) - n(a[valueField]); }).slice(0, limit || rows.length);
    var peak = max(rows, valueField);
    return '<div class="lci-bars">' + rows.map(function (row, index) {
      return '<div class="lci-bar"><span class="rank">' + String(index + 1).padStart(2, "0") + '</span><b>' + esc(row[labelField]) + '</b><i><em class="' + (colorClass || "") + '" style="width:' + (n(row[valueField]) / peak * 100).toFixed(1) + '%"></em></i><strong>' + valueFormat(n(row[valueField])) + '</strong></div>';
    }).join("") + '</div>';
  }
  function donut(rows, field, colors, formatter) {
    var total = sum(rows, field) || 1, angle = 0, stops = [];
    rows.forEach(function (row, index) {
      var end = angle + n(row[field]) / total * 360;
      stops.push(colors[index % colors.length] + ' ' + angle + 'deg ' + end + 'deg'); angle = end;
    });
    return '<div class="lci-donutwrap"><div class="lci-donut" style="background:conic-gradient(' + stops.join(",") + ')"><span><b>' + formatter(total) + '</b><small>total</small></span></div><div class="lci-legend">' + rows.map(function (row, index) {
      var label = row.sales_channel || row.product_group || row.segment || row.brand_solution || row.reject_reason;
      return '<div><i style="background:' + colors[index % colors.length] + '"></i><span>' + esc(label) + '</span><b>' + (n(row[field]) / total * 100).toFixed(1) + '%</b></div>';
    }).join("") + '</div></div>';
  }
  function sparkline(rows, field) {
    var values = rows.map(function (r) { return n(r[field]); }), lo = Math.min.apply(Math, values), hi = Math.max.apply(Math, values), w = 780, h = 150;
    var points = values.map(function (v, i) { var x = i / Math.max(values.length - 1, 1) * w; var y = h - 15 - (v - lo) / Math.max(hi - lo, 1) * (h - 30); return x.toFixed(1) + ',' + y.toFixed(1); }).join(' ');
    return '<svg class="lci-spark" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none"><defs><linearGradient id="lci-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b9d83" stop-opacity=".35"/><stop offset="1" stop-color="#0b9d83" stop-opacity="0"/></linearGradient></defs><polygon points="0,' + h + ' ' + points + ' ' + w + ',' + h + '" fill="url(#lci-area)"/><polyline points="' + points + '" fill="none" stroke="#0b9d83" stroke-width="3"/><line x1="0" y1="' + (h - 15) + '" x2="' + w + '" y2="' + (h - 15) + '" stroke="#dfe7e6"/><text x="4" y="14">' + esc(rows[0].month) + '</text><text x="' + (w - 62) + '" y="14">' + esc(rows[rows.length - 1].month) + '</text></svg>';
  }

  function executive() {
    var cleanRate = n(kpi.total_skus) / n(kpi.raw_rows) * 100;
    var topCats = categories.slice().sort(function (a, b) { return n(b.revenue_12m_zar) - n(a.revenue_12m_zar); }).slice(0, 6);
    var hero = '<section class="lci-hero"><div class="lci-hero-copy"><span>FROM FACTORY FLOOR TO RETAIL SHELF</span><h2>One portfolio.<br><b>Every commercial signal.</b></h2><p>A board-ready lens across catalog value, product mix, route-to-market, data quality and machine-learning controls.</p><div><strong>' + count(kpi.active_skus) + '</strong><small>active SKUs</small><strong>' + pct(cleanRate) + '</strong><small>clean-through rate</small></div></div></section>';
    var kpis = '<div class="lci-kpis">' + metric("trend", "teal", "MODELED CATALOG VALUE", money(kpi.revenue_12m_zar, true), "12-month aggregate") + metric("box", "blue", "CLEAN PRODUCT RECORDS", count(kpi.total_skus), "4.28m analytics-ready") + metric("factory", "copper", "STOCK FOOTPRINT", count(kpi.total_stock_units), "Units represented") + metric("shield", "gold", "QUARANTINED", count(kpi.quarantined_rows), "Traceable reject layer") + '</div>';
    var mix = card("Route-to-market mix", "Modeled 12-month value by commercial channel", donut(channels, "revenue_12m_zar", ["#0a8f78", "#2d6cdf", "#e56b2f", "#e6b422"], function (v) { return money(v, true); }), "lci-mix");
    var cat = card("Portfolio value leaders", "Top product categories by modeled value", bars(topCats, "category", "revenue_12m_zar", function (v) { return money(v, true); }, "teal", 6), "lci-leaders");
    return hero + kpis + '<div class="lci-grid two">' + cat + mix + '</div>';
  }

  function portfolio() {
    var ambient = categories.filter(function (r) { return r.product_group === "Ambient products"; });
    var perish = categories.filter(function (r) { return r.product_group === "Perishable products"; });
    var topBrands = brands.slice().sort(function (a, b) { return n(b.revenue_12m_zar) - n(a.revenue_12m_zar); }).slice(0, 10);
    var ambientValue = sum(ambient, "revenue_12m_zar"), perishValue = sum(perish, "revenue_12m_zar");
    var kpis = '<div class="lci-kpis">' + metric("box", "teal", "CATEGORIES", String(categories.length), "Across two product groups") + metric("factory", "copper", "AMBIENT PORTFOLIO", money(ambientValue, true), "Shelf-stable value") + metric("grid", "blue", "PERISHABLE PORTFOLIO", money(perishValue, true), "Cold-chain value") + metric("trend", "gold", "AVERAGE MARGIN", pct(kpi.avg_margin_pct), "Modeled portfolio mean") + '</div>';
    var matrix = '<div class="lci-category-grid">' + categories.slice().sort(function (a,b){return n(b.revenue_12m_zar)-n(a.revenue_12m_zar);}).map(function (r, i) {
      return '<article class="' + (r.product_group === "Ambient products" ? "ambient" : "perishable") + '"><span>' + String(i + 1).padStart(2,"0") + '</span><div><b>' + esc(r.category) + '</b><small>' + esc(r.product_group) + '</small></div><strong>' + money(r.revenue_12m_zar, true) + '</strong><em>' + count(r.sku_count) + ' SKUs</em></article>';
    }).join("") + '</div>';
    var categoriesCard = card("Category architecture", "Commercial value, group and scale in one operating view", matrix, "lci-category");
    var brandCard = card("Brand performance ladder", "Top ten brands by modeled catalog value", bars(topBrands, "brand", "revenue_12m_zar", function(v){return money(v,true);}, "copper", 10), "lci-brand");
    var groupRows = [{product_group:"Ambient products", revenue_12m_zar:ambientValue},{product_group:"Perishable products", revenue_12m_zar:perishValue}];
    var split = card("Manufacturing portfolio split", "Shelf-stable versus cold-chain exposure", donut(groupRows,"revenue_12m_zar",["#e56b2f","#2d6cdf"],function(v){return money(v,true);}) + '<div class="lci-callout"><b>Decision signal</b><p>Ambient products contribute ' + (ambientValue/(ambientValue+perishValue)*100).toFixed(1) + '% of modeled value, making plant reliability and dry-goods availability the dominant portfolio lever.</p></div>', "lci-split");
    return kpis + '<div class="lci-grid portfolio"><div>' + categoriesCard + '</div><div>' + brandCard + split + '</div></div>';
  }

  function network() {
    var totalValue = n(kpi.revenue_12m_zar), topProvince = provinces.slice().sort(function(a,b){return n(b.revenue_12m_zar)-n(a.revenue_12m_zar);})[0];
    var kpis = '<div class="lci-kpis">' + metric("map", "teal", "PROVINCES COVERED", String(provinces.length), "National commercial footprint") + metric("route", "blue", "SALES CHANNELS", String(channels.length), "Retail to export") + metric("trend", "copper", "LEADING PROVINCE", esc(topProvince.province), money(topProvince.revenue_12m_zar,true) + " modeled value") + metric("factory", "gold", "CONTRACT MANUFACTURING", money(channels[2].revenue_12m_zar,true), "Industrial channel") + '</div>';
    var mapRows = provinces.slice().sort(function(a,b){return n(b.revenue_12m_zar)-n(a.revenue_12m_zar);});
    var map = '<div class="lci-mapviz"><div class="lci-sa-shape"><span>ZA</span></div><div class="lci-maplist">' + mapRows.map(function(r,i){var share=n(r.revenue_12m_zar)/totalValue*100;return '<div><span>'+String(i+1).padStart(2,"0")+'</span><b>'+esc(r.province)+'</b><i><em style="width:'+share*2.6+'%"></em></i><strong>'+share.toFixed(1)+'%</strong><small>'+money(r.revenue_12m_zar,true)+'</small></div>';}).join("") + '</div></div>';
    var region = card("National value footprint", "Province share of modeled 12-month catalog value", map, "lci-region");
    var channel = card("Route-to-market architecture", "Scale, margin and value by channel", '<div class="lci-channelcards">' + channels.map(function(r,i){return '<article class="ch'+i+'"><span>'+icon(i===2?"factory":"route")+'</span><div><b>'+esc(r.sales_channel)+'</b><strong>'+money(r.revenue_12m_zar,true)+'</strong><small>'+count(r.sku_count)+' SKUs Â· '+pct(r.avg_margin_pct)+' margin</small></div></article>';}).join("") + '</div>', "lci-channels");
    return kpis + '<div class="lci-grid two network">' + region + channel + '</div>';
  }

  function dataQuality() {
    var rejected = sum(quality,"row_count"), clean = n(kpi.total_skus), raw = n(kpi.raw_rows), rate = clean/raw*100;
    var kpis = '<div class="lci-kpis">' + metric("grid","blue","RAW LANDING ZONE",count(raw),"Dirty product records") + metric("shield","teal","CLEAN ANALYTICS LAYER",count(clean),pct(rate)+" accepted") + metric("alert","copper","QUARANTINE LAYER",count(rejected),pct(rejected/raw)+" isolated") + metric("trend","gold","PIPELINE RECONCILIATION","100.0%","Clean + quarantine = raw") + '</div>';
    var funnel = '<div class="lci-funnel"><div class="raw"><b>'+count(raw)+'</b><span>RAW PRODUCTS</span></div><i>ADF validation</i><div class="clean"><b>'+count(clean)+'</b><span>CLEAN + CONFORMED</span></div><i>Synapse marts</i><div class="serve"><b>7</b><span>REPORTING AGGREGATES</span></div></div>';
    var funnelCard = card("Medallion control flow", "Every rejected row remains traceable", funnel + '<div class="lci-control-note"><b>Control passed</b><span>'+count(clean)+' + '+count(rejected)+' = '+count(raw)+'</span></div>', "lci-flow");
    var reasonCard = card("Why records were quarantined", "Reject combinations ranked by affected rows", bars(quality,"reject_reason","row_count",function(v){return count(v);},"copper",11), "lci-reasons");
    var growthCard = card("Catalog ingestion cadence", "Products added by month, Jan 2021â€“Jun 2026", sparkline(growth,"products_added") + '<div class="lci-growthstats"><span><b>'+count(sum(growth,"products_added"))+'</b> total additions</span><span><b>'+count(sum(growth,"products_added")/growth.length)+'</b> average/month</span><span><b>'+growth.length+'</b> reporting months</span></div>', "lci-growth");
    return kpis + '<div class="lci-grid quality"><div>'+funnelCard+growthCard+'</div>'+reasonCard+'</div>';
  }

  function mlLab() {
    var m = metrics.price_model;
    var kpis = '<div class="lci-kpis">' + metric("spark","teal","PRICE MODEL",esc(m.model),"Gradient-boosted regressor") + metric("trend","blue","VALIDATION RÂ²",n(m.r2).toFixed(4),"Out-of-sample explanatory power") + metric("alert","copper","MAE",money(m.mae_zar,false),"Mean absolute price error") + metric("search","gold","ANOMALIES FLAGGED",count(metrics.anomalies_flagged),"Decision-review queue") + '</div>';
    var gauge = '<div class="lci-gauge"><svg viewBox="0 0 240 140"><path d="M30 120a90 90 0 0 1 180 0" pathLength="100"/><path class="value" d="M30 120a90 90 0 0 1 180 0" pathLength="100" style="stroke-dasharray:'+n(m.r2)*100+' 100"/></svg><span><b>'+n(m.r2).toFixed(3)+'</b><small>validation RÂ²</small></span></div><div class="lci-modelmeta"><div><b>'+count(m.train_rows)+'</b><span>training rows</span></div><div><b>'+money(m.mean_price_zar,false)+'</b><span>mean price</span></div><div><b>'+money(m.mae_zar,false)+'</b><span>MAE</span></div></div>';
    var model = card("Model performance", "Directional pricing intelligence with transparent validation", gauge, "lci-model");
    var seg = card("Four product behavior segments", "Price, demand and margin archetypes", '<div class="lci-segments">'+segments.map(function(r,i){return '<article class="seg'+i+'"><span>0'+(i+1)+'</span><div><b>'+count(r.products)+' products</b><p>'+money(r.avg_price,false)+' avg price Â· '+pct(r.avg_margin_pct)+' margin</p></div><strong>'+money(r.revenue_12m,true)+'</strong><small>modeled value</small></article>';}).join("")+'</div>', "lci-segmentcard");
    var sample = anomalies.slice(0,7);
    var anomaly = card("Exception review sample", "High-deviation products ranked for commercial context", '<table class="lci-table"><thead><tr><th>Product</th><th>Category</th><th>Brand</th><th>Price</th><th>Margin</th><th>Review</th></tr></thead><tbody>'+sample.map(function(r){return '<tr><td><b>'+esc(r.product_name)+'</b><small>'+esc(r.product_id)+'</small></td><td>'+esc(r.category)+'</td><td>'+esc(r.brand)+'</td><td>'+money(r.price_zar,false)+'</td><td>'+pct(r.margin_pct)+'</td><td><span class="lci-pill">Commercial context</span></td></tr>';}).join("")+'</tbody></table>', "lci-anomaly");
    return kpis + '<div class="lci-grid ml"><div>'+model+seg+'</div>'+anomaly+'</div>';
  }

  function explorer() {
    var rows = anomalies.slice(0,30);
    var kpis = '<div class="lci-kpis">' + metric("search","teal","REVIEW UNIVERSE",count(metrics.anomalies_flagged),"ML-ranked exceptions") + metric("box","blue","CATEGORIES REPRESENTED",String(new Set(rows.map(function(r){return r.category;})).size),"In displayed sample") + metric("factory","copper","BRANDS REPRESENTED",String(new Set(rows.map(function(r){return r.brand;})).size),"Cross-portfolio view") + metric("shield","gold","DECISION RULE","Reviewâ€”not delete","Human context required") + '</div>';
    var filters = '<div class="lci-tools"><label>Find product<input type="search" class="lci-search" placeholder="Name, brand or category"></label><label>Category<select class="lci-cat"><option value="">All categories</option>'+Array.from(new Set(rows.map(function(r){return r.category;}))).sort().map(function(v){return '<option>'+esc(v)+'</option>';}).join("")+'</select></label><span><b>'+rows.length+'</b> sample rows shown</span></div>';
    var table = '<table class="lci-table explorer"><thead><tr><th>Product ID</th><th>Product</th><th>Category</th><th>Brand</th><th>Price</th><th>Cost</th><th>Margin</th><th>Signal</th></tr></thead><tbody>'+rows.map(function(r){return '<tr data-search="'+esc((r.product_name+' '+r.brand+' '+r.category).toLowerCase())+'" data-cat="'+esc(r.category)+'"><td>'+esc(r.product_id)+'</td><td><b>'+esc(r.product_name)+'</b></td><td>'+esc(r.category)+'</td><td>'+esc(r.brand)+'</td><td>'+money(r.price_zar,false)+'</td><td>'+money(r.cost_zar,false)+'</td><td>'+pct(r.margin_pct)+'</td><td><span class="lci-pill danger">'+n(r.anomaly_raw).toFixed(3)+'</span></td></tr>';}).join("")+'</tbody></table>';
    return kpis + card("Product exception explorer", "Search and filter the decision-review sample; exceptions are candidates for investigation, not automatic errors", filters + '<div class="lci-tablewrap">'+table+'</div>', "lci-explorer");
  }

  function renderPage(page) {
    var summaries = {
      exec: ["EXECUTIVE CONTROL TOWER", "Integrated performance from factory floor to customer channel."],
      portfolio: ["PORTFOLIO ARCHITECTURE", "Category, brand and manufacturing exposure through a commercial lens."],
      network: ["ROUTE-TO-MARKET", "National distribution signals across channels and provinces."],
      quality: ["TRUSTED DATA OPERATIONS", "Visible controls from raw landing zone to governed reporting marts."],
      ml: ["RESPONSIBLE MACHINE LEARNING", "Transparent pricing signals, segmentation and exception review."],
      explorer: ["EVIDENCE-LEVEL REVIEW", "A searchable product queue for analyst and commercial follow-up."]
    };
    var body = page === "portfolio" ? portfolio() : page === "network" ? network() : page === "quality" ? dataQuality() : page === "ml" ? mlLab() : page === "explorer" ? explorer() : executive();
    return '<div class="lci-shell">'+nav(page)+'<main class="lci-main">'+header(page,summaries[page][0],summaries[page][1])+'<div class="lci-content">'+body+'<footer>Source: synthetic Libstar-style product analytics case study Â· Exact aggregate reporting layer Â· Not affiliated with Libstar Holdings</footer></div></main></div>';
  }

  function bind($element) {
    $element.off("click.lci").on("click.lci", ".lci-navitem", function () {
      var page = $(this).data("page");
      if (sheetMap[page]) qlik.navigation.gotoSheet(sheetMap[page]);
    });
    $element.off("input.lci change.lci").on("input.lci change.lci", ".lci-search,.lci-cat", function () {
      var query = String($element.find(".lci-search").val() || "").toLowerCase();
      var category = String($element.find(".lci-cat").val() || "");
      $element.find(".lci-table.explorer tbody tr").each(function () {
        var $row = $(this), visible = (!query || String($row.data("search")).indexOf(query) >= 0) && (!category || String($row.data("cat")) === category);
        $row.toggle(visible);
      });
    });
  }

  return {
    initialProperties: { defaultPage: "exec", showTitles: false },
    definition: properties,
    support: { snapshot: true, export: false, exportData: false },
    paint: function ($element, layout) {
      var page = layout.defaultPage || "exec";
      if (!pageNames[page]) page = "exec";
      $element.html(renderPage(page));
      bind($element);
      return qlik.Promise.resolve();
    }
  };
});

