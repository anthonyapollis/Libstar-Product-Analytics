"""Export local extracts so the project runs with zero cloud dependencies.

Creates data/local/:
  products_clean_1m_sample.csv  - 1M-row stratified sample of the cleaned
                                  catalog (Qlik Sense Desktop-friendly size)
  products_quarantine.csv       - full quarantine with reject reasons
  + copies of the aggregate tables used by every report

The full 4.28M-row cleaned catalog remains locally in
data/curated/products_clean/*.parquet (canonical local copy).
"""

import glob
import os
import shutil

import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "local")
SEED = 42


def main() -> None:
    os.makedirs(OUT, exist_ok=True)

    files = glob.glob(os.path.join(BASE, "data", "curated", "products_clean", "*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    sample = df.groupby("category", observed=True).sample(
        frac=1_000_000 / len(df), random_state=SEED)
    assert "category" in sample.columns, "stratified sample dropped the category column"
    sample.to_csv(os.path.join(OUT, "products_clean_1m_sample.csv"), index=False)
    print(f"sample written: {len(sample):,} rows, columns: {list(sample.columns)}")

    qfiles = glob.glob(os.path.join(BASE, "data", "curated", "products_quarantine", "*.parquet"))
    q = pd.concat([pd.read_parquet(f) for f in qfiles], ignore_index=True)
    q.to_csv(os.path.join(OUT, "products_quarantine.csv"), index=False)
    print(f"quarantine written: {len(q):,} rows")

    for f in glob.glob(os.path.join(BASE, "data", "aggregates", "*.csv")):
        shutil.copy(f, OUT)
    ml_anoms = os.path.join(BASE, "ml", "outputs", "price_anomalies.csv")
    if os.path.exists(ml_anoms):
        shutil.copy(ml_anoms, OUT)
    print("aggregates + ml anomalies copied to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
