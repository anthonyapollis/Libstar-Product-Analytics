"""ML on the cleaned Libstar catalog (post-ADF curated parquet).

1. Price prediction  — HistGradientBoostingRegressor: predict price from
   category/brand/physical attributes. Shows how well catalog structure
   explains pricing (and which categories are mispriced).
2. Anomaly detection — IsolationForest per product on price/cost/margin/
   weight/rating; top anomalies exported for Qlik + the ebook.
3. Segmentation     — KMeans on price/margin/units/rating into 4 product
   segments (value drivers, premium niche, volume movers, long tail).

Inputs : data/curated/products_clean/*.parquet (downloaded from ADLS)
Outputs: ml/outputs/metrics.json, price_anomalies.csv, segments_summary.csv,
         ml_scored_sample.parquet (uploaded to curated/ml for Synapse/Qlik)
"""

import glob
import json
import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

BASE = os.path.join(os.path.dirname(__file__), "..")
CURATED = os.path.join(BASE, "data", "curated", "products_clean")
OUT = os.path.join(os.path.dirname(__file__), "outputs")
SEED = 42
TRAIN_SAMPLE = 600_000


def load() -> pd.DataFrame:
    files = glob.glob(os.path.join(CURATED, "*.parquet"))
    if not files:
        raise SystemExit(f"no parquet found in {CURATED} - download curated data first")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    print(f"loaded {len(df):,} cleaned rows from {len(files)} files")
    return df


def price_model(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["price_zar", "weight_kg", "rating"]).sample(
        min(TRAIN_SAMPLE, len(df)), random_state=SEED)
    cat_cols = ["product_group", "category", "brand", "brand_solution", "sales_channel"]
    num_cols = ["weight_kg", "rating", "stock_qty", "units_sold_12m"]
    X = d[cat_cols + num_cols]
    y = d["price_zar"]

    enc = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_cols),
    ], remainder="passthrough")
    Xe = enc.fit_transform(X)
    X_tr, X_te, y_tr, y_te = train_test_split(Xe, y, test_size=0.2, random_state=SEED)

    m = HistGradientBoostingRegressor(random_state=SEED, max_iter=200)
    m.fit(X_tr, y_tr)
    pred = m.predict(X_te)
    metrics = {
        "model": "HistGradientBoostingRegressor",
        "train_rows": int(len(X_tr)),
        "r2": round(float(r2_score(y_te, pred)), 4),
        "mae_zar": round(float(mean_absolute_error(y_te, pred)), 2),
        "mean_price_zar": round(float(y.mean()), 2),
    }
    print("price model:", metrics)
    return metrics


def anomalies(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["price_zar", "cost_zar", "margin_pct", "weight_kg"]).sample(
        min(1_000_000, len(df)), random_state=SEED).copy()
    feats = d[["price_zar", "cost_zar", "margin_pct", "weight_kg"]]
    iso = IsolationForest(n_estimators=100, contamination=0.005, random_state=SEED)
    d["anomaly_score"] = iso.fit_predict(feats)
    d["anomaly_raw"] = iso.decision_function(feats)
    anom = d[d["anomaly_score"] == -1].nsmallest(2000, "anomaly_raw")
    cols = ["product_id", "product_name", "category", "brand", "price_zar",
            "cost_zar", "margin_pct", "weight_kg", "anomaly_raw"]
    print(f"anomalies flagged: {len(anom):,} of {len(d):,} scored")
    return anom[cols]


def segments(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["price_zar", "margin_pct", "units_sold_12m", "rating"]).sample(
        min(500_000, len(df)), random_state=SEED).copy()
    feats = StandardScaler().fit_transform(
        d[["price_zar", "margin_pct", "units_sold_12m", "rating"]])
    km = KMeans(n_clusters=4, random_state=SEED, n_init=5)
    d["segment"] = km.fit_predict(feats)
    summary = d.groupby("segment").agg(
        products=("product_id", "count"),
        avg_price=("price_zar", "mean"),
        avg_margin_pct=("margin_pct", "mean"),
        avg_units_12m=("units_sold_12m", "mean"),
        avg_rating=("rating", "mean"),
        revenue_12m=("revenue_12m_zar", "sum"),
    ).round(2).reset_index()
    print(summary.to_string(index=False))
    return summary


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    df = load()

    metrics = {"rows_cleaned": int(len(df))}
    metrics["price_model"] = price_model(df)

    anom = anomalies(df)
    anom.to_csv(os.path.join(OUT, "price_anomalies.csv"), index=False)
    metrics["anomalies_flagged"] = int(len(anom))

    seg = segments(df)
    seg.to_csv(os.path.join(OUT, "segments_summary.csv"), index=False)

    anom.to_parquet(os.path.join(OUT, "ml_anomalies.parquet"), index=False)
    with open(os.path.join(OUT, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print("ML outputs written to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
