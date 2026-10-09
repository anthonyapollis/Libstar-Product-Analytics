"""Run the Bronze -> Silver -> Gold pipeline three times locally on PySpark + Delta Lake, as a demonstration.

notebooks/employee360_medallion.py runs employee360_incremental (Bronze, checks, issue lifecycle) and then
builds Silver and Gold.

    pip install "pyspark==4.0.*" "delta-spark==4.0.*"
    python run_incremental_local.py

Run 1 loads the supplied extracts (data/). Run 2 delivers the same files again: nothing is read or checked.
Run 3 delivers data/simulated_run3/ (labelled edits): some issues resolve and one new issue raises an alert.
Results are saved to outputs/incremental_*.csv. The local Delta warehouse is recreated on each demo.
"""
import csv
import re
import shutil
import sys
from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parent
NB = ROOT / "notebooks"
OUT = ROOT / "outputs"
WAREHOUSE = ROOT / ".local-warehouse"
SCHEMA = "employee360_dq"


class Skipped(Exception):
    pass


def cells(path):
    for cell in re.split(r"^# COMMAND ----------$", path.read_text(encoding="utf-8"), flags=re.M):
        yield cell


def run_notebook(path, ns):
    for cell in cells(path):
        s = cell.strip()
        if s.startswith("# MAGIC %run"):
            run_notebook(NB / (s.split("%run", 1)[1].strip().lstrip("./") + ".py"), ns)
        elif not s.startswith("# MAGIC"):
            exec(compile(cell, str(path), "exec"), ns)
            if ns.get("RUN_SUMMARY", {}).get("checks_run") is False:
                raise Skipped()


def main():
    shutil.rmtree(WAREHOUSE, ignore_errors=True)
    builder = (SparkSession.builder.master("local[2]").appName("employee360-dq-incremental")
               .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
               .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
               .config("spark.sql.warehouse.dir", str(WAREHOUSE))
               .config("spark.sql.shuffle.partitions", "4")
               .config("spark.sql.session.timeZone", "UTC")
               .config("spark.ui.enabled", "false")
               .config("spark.ui.showConsoleProgress", "false"))
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    snapshots = {}  # run number -> {name: (columns, rows)}, captured right after the run (tables change later)
    for run_no, batch_dir in enumerate(["data", "data", "data/simulated_run3"], start=1):
        print(f"\n{'=' * 100}\nRUN {run_no} with batch_dir={batch_dir}\n{'=' * 100}")
        ns = {"spark": spark, "PROJECT_ROOT": str(ROOT), "BATCH_DIR": batch_dir, "TARGET_SCHEMA": SCHEMA,
              "__name__": "__notebook__", "display": lambda df: df.show(100, truncate=False)}
        try:
            run_notebook(NB / "employee360_medallion.py", ns)
            snapshots[run_no] = {n: (ns["RESULTS"][n].columns, ns["RESULTS"][n].collect())
                                 for n in ("gold_employee_360", "layers", "gold_vs_delivered")}
        except Skipped:
            pass

    OUT.mkdir(exist_ok=True)
    # Run 1 is the supplied data (the real result); run 3 is the simulated delivery.
    for run_no, prefix in [(1, "medallion_"), (3, "medallion_run3_")]:
        for name, (columns, rows) in snapshots[run_no].items():
            with open(OUT / f"{prefix}{name}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, lineterminator="\n")
                w.writerow(columns)
                w.writerows([["" if v is None else (", ".join(v) if isinstance(v, list) else v) for v in r] for r in rows])
            print(f"wrote outputs/{prefix}{name}.csv ({len(rows)} rows)")
    for name, query in [
        ("incremental_runs", f"SELECT run_id, batch_dir, changed_employees, checks_run, new_issues, resolved_issues, open_issues FROM {SCHEMA}.dq_runs ORDER BY run_id"),
        ("incremental_batches", f"SELECT source, batch_id, rows_in_file, rows_inserted, rows_dropped, skipped FROM {SCHEMA}.ingest_batches ORDER BY batch_id, source"),
        ("incremental_issues", f"SELECT rule_id, employee_id, status, first_seen_run, last_seen_run, resolved_run, detail FROM {SCHEMA}.dq_issues ORDER BY status, rule_id, employee_id"),
    ]:
        df = spark.sql(query)
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
