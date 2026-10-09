# Databricks notebook source
# MAGIC %md
# MAGIC # Employee 360 DQ: incremental run
# MAGIC How the checks run in production without rescanning everything or repeating the same alerts:
# MAGIC 1. **Skip unchanged extracts.** An extract whose file hash matches the last loaded batch is not read again.
# MAGIC 2. **Incremental, idempotent load.** Changed extracts are `MERGE`d into append-only Delta bronze tables on a
# MAGIC    row hash. Reloading the same rows inserts nothing; each row records the first and last batch it was seen in.
# MAGIC 3. **Changed keys.** Employees with a new, changed or disappeared row are listed. No changes means no checks run.
# MAGIC 4. **Issue lifecycle.** Failures are `MERGE`d into `dq_issues` (open / resolved). Alerts go out only for
# MAGIC    issues that are new in this run, so a known problem does not page someone every day.
# MAGIC
# MAGIC The checks themselves are the ones in `employee360_dq` (run below with `%run`), unchanged.

# COMMAND ----------

import csv
import hashlib
import os
from functools import reduce

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window

ON_DATABRICKS = "DATABRICKS_RUNTIME_VERSION" in os.environ
if ON_DATABRICKS:
    dbutils.widgets.text("batch_dir", "data", "Folder with the three extracts, relative to the project")
    dbutils.widgets.text("target_schema", "workspace.employee360_dq", "Schema for Delta tables")
    BATCH_DIR = dbutils.widgets.get("batch_dir")
    TARGET_SCHEMA = dbutils.widgets.get("target_schema")
    nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    PROJECT_ROOT = os.path.dirname(os.path.dirname("/Workspace" + nb_path))
# Locally, run_incremental_local.py sets PROJECT_ROOT, BATCH_DIR and TARGET_SCHEMA.

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
SOURCES = {"hr": "HR_Source.csv", "payroll": "Payroll_Source.csv", "e360": "Employee_360.csv"}
spark.sql(f"""CREATE TABLE IF NOT EXISTS {TARGET_SCHEMA}.ingest_batches (
  source STRING, batch_id INT, file_sha256 STRING, rows_in_file INT, rows_inserted INT, rows_dropped INT,
  skipped BOOLEAN, loaded_at TIMESTAMP) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {TARGET_SCHEMA}.dq_runs (
  run_id INT, batch_dir STRING, changed_employees INT, checks_run BOOLEAN, new_issues INT, resolved_issues INT,
  open_issues INT, run_at TIMESTAMP) USING DELTA""")
RUN_ID = spark.sql(f"SELECT coalesce(max(run_id), 0) + 1 AS r FROM {TARGET_SCHEMA}.dq_runs").first()["r"]
run_batches = {r["source"]: r["batch_id"] for r in
               spark.sql(f"SELECT source, max(batch_id) AS batch_id FROM {TARGET_SCHEMA}.ingest_batches GROUP BY source").collect()}
print(f"run {RUN_ID}, batch folder: {BATCH_DIR}")

# COMMAND ----------

def ingest(source, file_name):
    """Load one extract into bronze_<source> incrementally. Returns the batch log row."""
    path = os.path.join(PROJECT_ROOT, BATCH_DIR, file_name)
    raw = open(path, "rb").read()
    file_sha = hashlib.sha256(raw).hexdigest()
    prev_batch = run_batches.get(source, 0)
    last = spark.sql(f"""SELECT file_sha256 FROM {TARGET_SCHEMA}.ingest_batches
                         WHERE source = '{source}' AND NOT skipped ORDER BY batch_id DESC LIMIT 1""").collect()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    if last and last[0]["file_sha256"] == file_sha:
        return (source, prev_batch, file_sha, len(rows), 0, 0, True)   # same file as last time: nothing read

    batch = prev_batch + 1
    cols = list(rows[0].keys())
    schema = T.StructType([T.StructField(c, T.StringType()) for c in cols] + [T.StructField("_line", T.StringType())])
    df = spark.createDataFrame([[r[c] for c in cols] + [str(i + 2)] for i, r in enumerate(rows)], schema)
    # Row identity = hash of the business columns + its occurrence number, so an exact duplicate row in one
    # file is kept (and still caught by the uniqueness check) instead of collapsing into one.
    df = (df.withColumn("row_hash", F.sha2(F.concat_ws("\u0001", *[F.coalesce(F.col(c), F.lit("")) for c in cols]), 256))
            .withColumn("dup_seq", F.row_number().over(
                Window.partitionBy("row_hash").orderBy(F.col("_line").cast("int"))))
            .withColumn("first_batch", F.lit(batch)).withColumn("last_batch", F.lit(batch)))
    table = f"{TARGET_SCHEMA}.bronze_{source}"
    if not spark.catalog.tableExists(table):
        df.limit(0).write.format("delta").saveAsTable(table)
    before = spark.table(table).count()
    (DeltaTable.forName(spark, table).alias("t")
        .merge(df.alias("s"), "t.row_hash = s.row_hash AND t.dup_seq = s.dup_seq")
        .whenMatchedUpdate(set={"last_batch": "s.last_batch", "_line": "s._line"})
        .whenNotMatchedInsertAll()
        .execute())
    inserted = spark.table(table).count() - before
    dropped = spark.table(table).where(f"last_batch = {prev_batch}").count() if prev_batch else 0
    return (source, batch, file_sha, len(rows), inserted, dropped, False)


log = [ingest(s, f) for s, f in SOURCES.items()]
log_df = (spark.createDataFrame(log, "source string, batch_id int, file_sha256 string, rows_in_file int, "
                                     "rows_inserted int, rows_dropped int, skipped boolean")
          .withColumn("loaded_at", F.current_timestamp()))
log_df.where("NOT skipped").write.format("delta").mode("append").saveAsTable(f"{TARGET_SCHEMA}.ingest_batches")
display(log_df.drop("file_sha256"))

# COMMAND ----------

# Current snapshot of each source = the rows seen in its latest loaded batch. Changed keys = employees with a
# row that is new in this batch, or a row that was in the previous batch and is no longer delivered.
changed = []
for source in SOURCES:
    current = spark.sql(f"SELECT max(batch_id) AS b FROM {TARGET_SCHEMA}.ingest_batches WHERE source = '{source}' AND NOT skipped").first()["b"]
    bronze = spark.table(f"{TARGET_SCHEMA}.bronze_{source}")
    business = [c for c in bronze.columns if c not in ("row_hash", "dup_seq", "first_batch", "last_batch")]
    bronze.where(F.col("last_batch") == current).select(*business).createOrReplaceTempView(f"raw_{source}")
    this_run = next(r for r in log if r[0] == source)
    if not this_run[6]:  # loaded in this run
        changed.append(bronze.where(F.col("first_batch") == current).select("employee_id"))
        changed.append(bronze.where(F.col("last_batch") == current - 1).select("employee_id"))
changed_keys = (reduce(lambda a, b: a.unionByName(b), changed).distinct() if changed
                else spark.createDataFrame([], "employee_id string"))
CHANGED_COUNT = changed_keys.count()
print(f"employees with a change this run: {CHANGED_COUNT}")

# COMMAND ----------

if CHANGED_COUNT == 0:
    print("No source changed since the last run: checks skipped, no compute spent, no alerts.")
    RUN_SUMMARY = {"changed_employees": 0, "checks_run": False, "new_issues": 0, "resolved_issues": 0,
                   "open_issues": spark.table(f"{TARGET_SCHEMA}.dq_issues").where("status = 'Open'").count()
                   if spark.catalog.tableExists(f"{TARGET_SCHEMA}.dq_issues") else 0}
    spark.createDataFrame([(RUN_ID, BATCH_DIR, *RUN_SUMMARY.values())],
                          "run_id int, batch_dir string, changed_employees int, checks_run boolean, new_issues int, "
                          "resolved_issues int, open_issues int").withColumn("run_at", F.current_timestamp()) \
        .write.format("delta").mode("append").saveAsTable(f"{TARGET_SCHEMA}.dq_runs")
    if ON_DATABRICKS:
        dbutils.notebook.exit("skipped: no changes")
else:
    RAW_VIEWS_READY = True

# COMMAND ----------

# MAGIC %run ./employee360_dq

# COMMAND ----------

# Issue lifecycle: one row per (rule, employee). New failures open an issue (and alert); issues that no longer
# fail are resolved; issues still failing just get their last_seen updated (no repeat alert).
run_id = RUN_ID
current_issues = (RESULTS["failure_detail"].groupBy("rule_id", "employee_id")
                  .agg(F.array_join(F.array_sort(F.collect_set("detail")), "; ").alias("detail"))
                  .withColumn("run_id", F.lit(run_id)))
issues_table = f"{TARGET_SCHEMA}.dq_issues"
if not spark.catalog.tableExists(issues_table):
    spark.createDataFrame([], "rule_id string, employee_id string, detail string, status string, first_seen_run int, "
                              "last_seen_run int, resolved_run int").write.format("delta").saveAsTable(issues_table)
before = {(r["rule_id"], r["employee_id"]) for r in spark.table(issues_table).where("status = 'Open'").collect()}
(DeltaTable.forName(spark, issues_table).alias("t")
    .merge(current_issues.alias("s"), "t.rule_id = s.rule_id AND t.employee_id = s.employee_id AND t.status = 'Open'")
    .whenMatchedUpdate(set={"last_seen_run": "s.run_id", "detail": "s.detail"})
    .whenNotMatchedInsert(values={"rule_id": "s.rule_id", "employee_id": "s.employee_id", "detail": "s.detail",
                                  "status": F.lit("Open"), "first_seen_run": "s.run_id", "last_seen_run": "s.run_id",
                                  "resolved_run": F.lit(None).cast("int")})
    .whenNotMatchedBySourceUpdate(condition="t.status = 'Open'",
                                  set={"status": F.lit("Resolved"), "resolved_run": F.lit(run_id)})
    .execute())
issues = spark.table(issues_table)
new_issues = issues.where(f"status = 'Open' AND first_seen_run = {run_id}")
if before:  # on the first run every issue is new; alert on the monitoring summary instead of each one
    alerts = new_issues.join(spark.createDataFrame(RULES, "rule_id string, rule string, dimension string, severity string, "
                                                          "action string, alert_threshold int, owner string"), "rule_id")
    print("New issues this run (these are the alerts):")
    display(alerts.select("rule_id", "employee_id", "severity", "owner", "detail"))
RUN_SUMMARY = {
    "changed_employees": CHANGED_COUNT, "checks_run": True,
    "new_issues": new_issues.count(),
    "resolved_issues": issues.where(f"resolved_run = {run_id}").count(),
    "open_issues": issues.where("status = 'Open'").count(),
}
print(RUN_SUMMARY)
spark.createDataFrame([(RUN_ID, BATCH_DIR, *RUN_SUMMARY.values())],
                      "run_id int, batch_dir string, changed_employees int, checks_run boolean, new_issues int, "
                      "resolved_issues int, open_issues int").withColumn("run_at", F.current_timestamp()) \
    .write.format("delta").mode("append").saveAsTable(f"{TARGET_SCHEMA}.dq_runs")
display(issues.orderBy("status", "rule_id", "employee_id"))
