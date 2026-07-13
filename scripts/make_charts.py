"""Render ebook charts + shared aggregates from the curated Libstar catalog.

Outputs:
  ebook/charts/*.png          (300 dpi, consistent corporate style)
  data/aggregates/*.csv       (the exact tables the Excel report + ebook use,
                               computed once so every deliverable aligns)
"""

import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection

BASE = os.path.join(os.path.dirname(__file__), "..")
CHARTS = os.path.join(BASE, "ebook", "charts")
AGG = os.path.join(BASE, "data", "aggregates")

NAVY = "#1b2a4a"
TEAL = "#2a9d8f"
GOLD = "#e9c46a"
CORAL = "#e76f51"
GREY = "#8d99ae"
GROUP_COLORS = {"Perishable products": TEAL, "Ambient products": NAVY}
SOLUTION_COLORS = {
    "Libstar Brands": NAVY,
    "Principal Brands": TEAL,
    "Private label and dealer-own brands": GOLD,
}

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#cccccc",
    "axes.grid": True,
    "grid.color": "#e8e8e8",
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
})


def bn(x):  # billions formatter
    return f"R{x / 1e9:,.1f}bn"


def save(fig, name):
    path = os.path.join(CHARTS, name)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("chart:", name)


def load_clean() -> pd.DataFrame:
    files = glob.glob(os.path.join(BASE, "data", "curated", "products_clean", "*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["date_added"] = pd.to_datetime(df["date_added"])
    print(f"clean rows: {len(df):,}")
    return df


def load_quarantine() -> pd.DataFrame:
    files = glob.glob(os.path.join(BASE, "data", "curated", "products_quarantine", "*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def main() -> None:
    os.makedirs(CHARTS, exist_ok=True)
    os.makedirs(AGG, exist_ok=True)
    df = load_clean()
    q = load_quarantine()

    # ---------- shared aggregates ----------
    kpi = pd.DataFrame([{
        "total_skus": len(df),
        "active_skus": int((df["is_active"] == True).sum()),  # noqa: E712
        "revenue_12m_zar": round(float(df["revenue_12m_zar"].sum()), 2),
        "avg_margin_pct": round(float(df["margin_pct"].mean()), 2),
        "avg_price_zar": round(float(df["price_zar"].mean()), 2),
        "avg_rating": round(float(df["rating"].mean()), 2),
        "total_stock_units": int(df["stock_qty"].sum()),
        "quarantined_rows": len(q),
        "raw_rows": len(df) + len(q),  # post-dedupe approximation noted in ebook
    }])
    kpi.to_csv(os.path.join(AGG, "kpi_summary.csv"), index=False)

    cat = (df.groupby(["product_group", "category"], observed=True)
             .agg(sku_count=("product_id", "count"),
                  revenue_12m_zar=("revenue_12m_zar", "sum"),
                  avg_margin_pct=("margin_pct", "mean"),
                  avg_price_zar=("price_zar", "mean"),
                  avg_rating=("rating", "mean"))
             .round(2).reset_index()
             .sort_values("revenue_12m_zar", ascending=False))
    cat.to_csv(os.path.join(AGG, "category_performance.csv"), index=False)

    brand = (df.groupby(["brand_solution", "brand"], observed=True)
               .agg(sku_count=("product_id", "count"),
                    revenue_12m_zar=("revenue_12m_zar", "sum"),
                    avg_margin_pct=("margin_pct", "mean"),
                    avg_rating=("rating", "mean"))
               .round(2).reset_index()
               .sort_values("revenue_12m_zar", ascending=False))
    brand.to_csv(os.path.join(AGG, "brand_performance.csv"), index=False)

    provp = (df.groupby("province", observed=True)
               .agg(sku_count=("product_id", "count"),
                    revenue_12m_zar=("revenue_12m_zar", "sum"),
                    avg_margin_pct=("margin_pct", "mean"))
               .round(2).reset_index())
    provp.to_csv(os.path.join(AGG, "province_performance.csv"), index=False)

    chan = (df.groupby("sales_channel", observed=True)
              .agg(sku_count=("product_id", "count"),
                   revenue_12m_zar=("revenue_12m_zar", "sum"),
                   avg_margin_pct=("margin_pct", "mean"))
              .round(2).reset_index()
              .sort_values("revenue_12m_zar", ascending=False))
    chan.to_csv(os.path.join(AGG, "channel_performance.csv"), index=False)

    dq = q["reject_reason"].value_counts().reset_index()
    dq.columns = ["reject_reason", "row_count"]
    dq.to_csv(os.path.join(AGG, "data_quality.csv"), index=False)

    growth = (df.assign(month=df["date_added"].dt.to_period("M").astype(str))
                .groupby("month").size().reset_index(name="products_added"))
    growth.to_csv(os.path.join(AGG, "catalog_growth.csv"), index=False)

    # ---------- 1. revenue by category ----------
    fig, ax = plt.subplots(figsize=(10, 6))
    d = cat.sort_values("revenue_12m_zar")
    colors = [GROUP_COLORS[g] for g in d["product_group"]]
    ax.barh(d["category"], d["revenue_12m_zar"] / 1e9, color=colors)
    ax.set_xlabel("Revenue, last 12 months (R billions)")
    ax.set_title("Revenue by category — Ambient does the heavy lifting")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in GROUP_COLORS.values()]
    ax.legend(handles, GROUP_COLORS.keys(), loc="lower right", frameon=False)
    save(fig, "01_revenue_by_category.png")

    # ---------- 2. margin by category ----------
    fig, ax = plt.subplots(figsize=(10, 6))
    d = cat.sort_values("avg_margin_pct")
    ax.barh(d["category"], d["avg_margin_pct"], color=[GROUP_COLORS[g] for g in d["product_group"]])
    ax.axvline(df["margin_pct"].mean(), color=CORAL, ls="--", lw=1.5,
               label=f"portfolio avg {df['margin_pct'].mean():.1f}%")
    ax.set_xlabel("Average margin %")
    ax.set_title("Margin by category")
    ax.legend(frameon=False)
    save(fig, "02_margin_by_category.png")

    # ---------- 3. top brands ----------
    fig, ax = plt.subplots(figsize=(10, 7))
    d = brand.head(15).sort_values("revenue_12m_zar")
    ax.barh(d["brand"], d["revenue_12m_zar"] / 1e9,
            color=[SOLUTION_COLORS[s] for s in d["brand_solution"]])
    ax.set_xlabel("Revenue, last 12 months (R billions)")
    ax.set_title("Top 15 brands by revenue")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in SOLUTION_COLORS.values()]
    ax.legend(handles, SOLUTION_COLORS.keys(), loc="lower right", frameon=False, fontsize=9)
    save(fig, "03_top_brands.png")

    # ---------- 4. product group + channel mix ----------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5))
    g = df.groupby("product_group", observed=True)["revenue_12m_zar"].sum()
    ax1.pie(g, labels=g.index, autopct=lambda p: f"{p:.0f}%",
            colors=[GROUP_COLORS[i] for i in g.index], startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 2})
    ax1.set_title("Revenue split by product group")
    d = chan.sort_values("revenue_12m_zar")
    ax2.barh(d["sales_channel"], d["revenue_12m_zar"] / 1e9, color=TEAL)
    ax2.set_xlabel("Revenue (R billions)")
    ax2.set_title("Revenue by sales channel")
    save(fig, "04_group_channel_mix.png")

    # ---------- 5. SA province map ----------
    with open(os.path.join(BASE, "data", "reference", "za_provinces.geojson"), encoding="utf-8") as f:
        gj = json.load(f)
    rev = provp.set_index("province")["revenue_12m_zar"]
    vmin, vmax = rev.min(), rev.max()
    cmap = plt.cm.YlGnBu
    fig, ax = plt.subplots(figsize=(12, 10))
    for ft in gj["features"]:
        name = ft["properties"]["name"]
        val = rev.get(name, np.nan)
        color = cmap(0.15 + 0.8 * (val - vmin) / (vmax - vmin)) if not np.isnan(val) else "#eeeeee"
        geom = ft["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        patches = []
        for poly in polys:
            for ring in poly[:1]:  # outer ring
                patches.append(MplPolygon(np.array(ring)))
        pc = PatchCollection(patches, facecolor=color, edgecolor="white", linewidth=1.2)
        ax.add_collection(pc)
        # label at centroid of largest ring; small provinces get offset labels
        offsets = {"Gauteng": (-2.6, 1.9), "Mpumalanga": (2.0, 1.4)}
        largest = max((p[0] for p in polys), key=len)
        arr = np.array(largest)
        cx, cy = arr[:, 0].mean(), arr[:, 1].mean()
        label = f"{name}\n{bn(val)}" if not np.isnan(val) else name
        if name in offsets:
            dx, dy = offsets[name]
            ax.annotate(label, (cx, cy), xytext=(cx + dx, cy + dy),
                        ha="center", va="center", fontsize=8.5, color="#222222",
                        weight="bold",
                        arrowprops={"arrowstyle": "-", "color": "#555555", "lw": 0.9})
        else:
            ax.annotate(label, (cx, cy), ha="center", va="center", fontsize=8.5,
                        color="#222222", weight="bold")
    ax.set_xlim(15.5, 33.5)
    ax.set_ylim(-35.5, -21.5)
    ax.set_aspect(1.15)
    ax.axis("off")
    ax.set_title("Libstar 12-month revenue by province", fontsize=16, weight="bold", pad=14)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin / 1e9, vmax / 1e9))
    cb = fig.colorbar(sm, ax=ax, shrink=0.55, pad=0.02)
    cb.set_label("Revenue (R billions)")
    save(fig, "05_sa_province_map.png")

    # ---------- 6. data quality funnel ----------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    stages = ["Raw rows\n(with dupes)", "Passed validation", "Unique clean\nproducts"]
    raw_total = 5_100_000
    vals = [raw_total, raw_total - len(q), len(df)]
    bars = ax1.bar(stages, vals, color=[GREY, GOLD, TEAL])
    for b, v in zip(bars, vals):
        ax1.annotate(f"{v:,}", (b.get_x() + b.get_width() / 2, v), ha="center",
                     va="bottom", weight="bold")
    ax1.set_title("From raw to clean (ADF data flow)")
    ax1.set_ylabel("rows")
    top = dq.head(8).sort_values("row_count")
    ax2.barh(top["reject_reason"].str.rstrip(";"), top["row_count"], color=CORAL)
    ax2.set_title("Why rows were quarantined")
    ax2.set_xlabel("rows")
    save(fig, "06_data_quality.png")

    # ---------- 7. catalog growth ----------
    fig, ax = plt.subplots(figsize=(11, 5))
    g = growth.sort_values("month")
    ax.plot(pd.to_datetime(g["month"]), g["products_added"], color=NAVY, lw=1.8)
    ax.fill_between(pd.to_datetime(g["month"]), g["products_added"], color=NAVY, alpha=0.12)
    ax.set_title("Catalog additions per month")
    ax.set_ylabel("products added")
    save(fig, "07_catalog_growth.png")

    # ---------- 8. ML charts (if outputs exist) ----------
    seg_path = os.path.join(BASE, "ml", "outputs", "segments_summary.csv")
    anom_path = os.path.join(BASE, "ml", "outputs", "price_anomalies.csv")
    if os.path.exists(seg_path):
        seg = pd.read_csv(seg_path)
        fig, ax = plt.subplots(figsize=(10, 6))
        sc = ax.scatter(seg["avg_price"], seg["avg_margin_pct"],
                        s=seg["products"] / seg["products"].max() * 2500,
                        c=[NAVY, TEAL, GOLD, CORAL][:len(seg)], alpha=0.75)
        for _, r in seg.iterrows():
            ax.annotate(f"Segment {int(r['segment'])}\n{int(r['products']):,} products",
                        (r["avg_price"], r["avg_margin_pct"]), ha="center", fontsize=9,
                        weight="bold", color="white")
        ax.set_xlabel("Average price (R)")
        ax.set_ylabel("Average margin %")
        ax.set_title("Product segments (KMeans on price, margin, volume, rating)")
        save(fig, "08_ml_segments.png")
    if os.path.exists(anom_path):
        anom = pd.read_csv(anom_path)
        samp = df.sample(30_000, random_state=1)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(samp["price_zar"], samp["margin_pct"], s=4, color=GREY, alpha=0.25,
                   label="normal (sample)")
        ax.scatter(anom["price_zar"], anom["margin_pct"], s=14, color=CORAL,
                   label="flagged anomaly")
        ax.set_xlabel("Price (R)")
        ax.set_ylabel("Margin %")
        ax.set_title("IsolationForest price anomalies")
        ax.legend(frameon=False)
        save(fig, "09_ml_anomalies.png")

    print("aggregates:", os.path.abspath(AGG))


if __name__ == "__main__":
    main()
