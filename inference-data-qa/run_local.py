"""Run the Databricks notebook locally on open-source PySpark and save every result to outputs/.

    pip install "pyspark==4.0.*"
    python run_local.py

The notebook's cells run in order in one namespace, as on Databricks; Markdown cells are skipped.
"""
import csv
import re
import sys
from pathlib import Path

from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "notebooks" / "employee360_dq.py"
OUT = ROOT / "outputs"


def main():
    spark = (SparkSession.builder.master("local[2]").appName("employee360-dq")
             .config("spark.sql.shuffle.partitions", "4")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.ui.enabled", "false")
             .config("spark.ui.showConsoleProgress", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    ns = {"spark": spark, "PROJECT_ROOT": str(ROOT), "__name__": "__notebook__"}
    cells = re.split(r"^# COMMAND ----------$", NOTEBOOK.read_text(encoding="utf-8"), flags=re.M)
    for cell in cells:
        if cell.strip().startswith("# MAGIC"):
            continue
        exec(compile(cell, str(NOTEBOOK), "exec"), ns)

    OUT.mkdir(exist_ok=True)
    for name, df in ns["RESULTS"].items():
        rows = df.collect()
        with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(df.columns)
            w.writerows([["" if v is None else v for v in r] for r in rows])
        print(f"wrote outputs/{name}.csv ({len(rows)} rows)")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
