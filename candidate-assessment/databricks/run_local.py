"""Run the Databricks notebooks locally with open-source Spark + Delta Lake, as a test.

Executes each notebook's cells in order in one Python namespace (like a Databricks notebook),
following `# MAGIC %run ./x` and skipping Markdown cells. Needs: pip install "pyspark==4.0.*" "delta-spark==4.0.*"
Usage: python run_local.py [notebook ...]      (default: all, in order)
"""
import re
import sys
import time
from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

HERE = Path(__file__).resolve().parent / "notebooks"
WAREHOUSE = Path(__file__).resolve().parent / ".local-warehouse"


def spark_session():
    b = (SparkSession.builder.master("local[2]").appName("jsb-local")
         .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
         .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
         .config("spark.sql.warehouse.dir", str(WAREHOUSE))
         .config("spark.sql.shuffle.partitions", "4")
         .config("spark.ui.enabled", "false"))
    spark = configure_spark_with_delta_pip(b).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def run(path, ns):
    for cell in path.read_text(encoding="utf-8").split("# COMMAND ----------"):
        lines = [l for l in cell.splitlines() if l.strip() and l.strip() != "# Databricks notebook source"]
        if not lines:
            continue
        m = re.match(r"# MAGIC %run \./(\S+)", lines[0])
        if m:
            run(HERE / f"{m.group(1)}.py", ns)
            continue
        if all(l.startswith("# MAGIC") for l in lines):
            continue                                   # Markdown cell
        exec(compile(cell, str(path), "exec"), ns)


def main():
    spark = spark_session()
    names = sys.argv[1:] or ["01_exercise1_reconciliation", "02_exercise2_incremental_ingestion", "03_exercise3_schema"]
    for name in names:
        print(f"\n######## {name} ########", flush=True)
        t = time.time()
        run(HERE / f"{name}.py", {"spark": spark, "__name__": "notebook"})
        print(f"######## {name}: OK in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
