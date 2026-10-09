# Databricks notebook source
# MAGIC %md
# MAGIC # Employee 360 data-quality checks
# MAGIC Profiles the HR, payroll and Employee 360 extracts, runs six data-quality checks, reconciles the
# MAGIC sources to Employee 360 and produces one monitoring table (rule, pass/fail, severity, affected IDs).
# MAGIC
# MAGIC The SQL lives in `../sql/` and runs unchanged here and in local PySpark (`run_local.py`).
# MAGIC The field-level reconciliation is PySpark (`reconcile_fields`).

# COMMAND ----------

import csv
import os
from functools import reduce

from pyspark.sql import functions as F
from pyspark.sql import types as T

ON_DATABRICKS = "DATABRICKS_RUNTIME_VERSION" in os.environ

if ON_DATABRICKS:
    dbutils.widgets.text("as_of_date", "2026-10-08", "Extract date")
    dbutils.widgets.text("snapshot_end", "2026-10-31", "Last day of reporting month")
    dbutils.widgets.text("target_schema", "workspace.employee360_dq", "Schema for result tables")
    dbutils.widgets.dropdown("fail_on_block", "false", ["true", "false"], "Fail the job if a blocking rule fails")
    AS_OF_DATE = dbutils.widgets.get("as_of_date")
    SNAPSHOT_END = dbutils.widgets.get("snapshot_end")
    TARGET_SCHEMA = dbutils.widgets.get("target_schema")
    FAIL_ON_BLOCK = dbutils.widgets.get("fail_on_block") == "true"
    nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    PROJECT_ROOT = os.path.dirname(os.path.dirname("/Workspace" + nb_path))
else:
    # run_local.py sets PROJECT_ROOT before running this file.
    AS_OF_DATE = globals().get("AS_OF_DATE", "2026-10-08")
    SNAPSHOT_END = globals().get("SNAPSHOT_END", "2026-10-31")
    TARGET_SCHEMA, FAIL_ON_BLOCK = globals().get("TARGET_SCHEMA"), False
    display = lambda df: df.show(100, truncate=False)  # noqa: E731

PARAMS = {"as_of_date": AS_OF_DATE, "snapshot_end": SNAPSHOT_END}
RESULTS = {}  # name -> DataFrame, written out at the end
print(f"project root {PROJECT_ROOT}; extract date {AS_OF_DATE}; reporting month ends {SNAPSHOT_END}")

# COMMAND ----------

# MAGIC %md ## Load the extracts as delivered
# MAGIC Every column is read as a string, so typing happens in SQL where a bad value stays visible.
# MAGIC `_line` keeps each row's position in the file (used to show duplicates in delivery order).

# COMMAND ----------

def load_raw(file_name, view_name):
    with open(os.path.join(PROJECT_ROOT, "data", file_name), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys())
    schema = T.StructType([T.StructField(c, T.StringType()) for c in cols] + [T.StructField("_line", T.StringType())])
    data = [[r[c] for c in cols] + [str(i + 2)] for i, r in enumerate(rows)]
    df = spark.createDataFrame(data, schema)
    df.createOrReplaceTempView(view_name)
    return df.count()

# The incremental notebook builds raw_hr / raw_payroll / raw_e360 from its Delta bronze tables and sets
# RAW_VIEWS_READY before running this one; on its own, this notebook reads the CSVs directly.
if not globals().get("RAW_VIEWS_READY"):
    for file_name, view in [("HR_Source.csv", "raw_hr"), ("Payroll_Source.csv", "raw_payroll"), ("Employee_360.csv", "raw_e360")]:
        print(f"{file_name}: {load_raw(file_name, view)} rows -> {view}")

# COMMAND ----------

def run_sql_file(name, keep=()):
    """Run each statement in sql/<name>. SELECT results are displayed; `keep` names them, in order."""
    with open(os.path.join(PROJECT_ROOT, "sql", name), encoding="utf-8") as f:
        text = f.read()
    for k, v in PARAMS.items():
        text = text.replace("${" + k + "}", v)
    statements = [s.strip() for s in text.split(";\n") if s.strip().rstrip(";").strip()]
    keep = list(keep)
    for s in statements:
        body = "\n".join(l for l in s.splitlines() if not l.strip().startswith("--")).strip().rstrip(";")
        if not body:
            continue
        df = spark.sql(body)
        if body.upper().startswith(("SELECT", "WITH")):
            label = keep.pop(0) if keep else None
            title = next((l.strip("- ").strip() for l in s.splitlines() if l.strip().startswith("--")), "")
            print("\n" + (title or label or name))
            display(df)
            if label:
                RESULTS[label] = df

run_sql_file("00_staging.sql")

# COMMAND ----------

# MAGIC %md ## 1. Profile

# COMMAND ----------

run_sql_file("01_profile.sql", keep=["profile_counts", "profile_nulls", "profile_duplicates", "profile_freshness", "profile_patterns"])

# COMMAND ----------

# MAGIC %md ## 2. Data-quality checks (each returns the affected employee IDs)

# COMMAND ----------

run_sql_file("02_checks.sql", keep=["check_failures"])

# COMMAND ----------

# MAGIC %md ## 3. Reconciliation: keys and totals (SQL), then fields (PySpark)

# COMMAND ----------

run_sql_file("03_reconciliation.sql", keep=["recon_keys", "recon_counts", "recon_salary_totals", "recon_lookalike"])

# COMMAND ----------

# Which system owns each field (from the brief): HR owns status, manager, department, location;
# payroll owns salary and payroll status. Severity reflects the business use of the field.
FIELD_RULES = [
    # field,              owner,     severity
    ("employment_status", "HR",      "Critical"),
    ("monthly_salary",    "Payroll", "Critical"),
    ("currency",          "Payroll", "Critical"),
    ("department",        "HR",      "High"),
    ("manager_id",        "HR",      "High"),
    ("location",          "HR",      "High"),
    ("full_name",         "HR",      "Medium"),
    ("effective_date",    "HR",      "Medium"),
]


def reconcile_fields(hr, payroll, e360, snapshot_end):
    """Compare every business-critical field in Employee 360 with its system of record.

    Returns one row per difference, classified as an error or a legitimate exception, with the reason.
    Only employees present in both HR and Employee 360 are compared; missing and unexpected
    employees are handled by the key reconciliation.
    """
    # The first row per employee in file order (key_occurrence comes from row_number() in 00_staging.sql),
    # plus how many distinct values payroll holds for each field, so a conflicting duplicate is visible.
    first_row = payroll.where("key_occurrence = 1").select("employee_id", "monthly_salary", "currency")
    spread = (payroll.groupBy("employee_id")
              .agg(F.count("*").alias("payroll_rows"),
                   F.countDistinct("monthly_salary").alias("n_monthly_salary"),
                   F.countDistinct("currency").alias("n_currency"),
                   F.array_join(F.transform(F.array_sort(F.collect_list(F.struct("key_occurrence", "monthly_salary"))),
                                            lambda s: s["monthly_salary"].cast("string")), " / ").alias("payroll_salaries")))
    pay = first_row.join(spread, "employee_id")
    src = hr.alias("h").join(pay.alias("p"), "employee_id", "left")
    joined = src.join(e360.alias("e"), "employee_id", "inner")

    diffs = []
    for field, owner, severity in FIELD_RULES:
        source_col = F.col(f"p.{field}") if owner == "Payroll" else F.col(f"h.{field}")
        target_col = F.col(f"e.{field}")
        differs = ~source_col.eqNullSafe(target_col)
        if owner == "Payroll":  # payroll holds more than one value: cannot verify, whatever Employee 360 shows
            differs = differs | (F.coalesce(F.col(f"p.n_{field}"), F.lit(0)) > 1)
        diffs.append(
            joined.where(differs)
            .select("employee_id",
                    F.lit(field).alias("field"), F.lit(owner).alias("system_of_record"), F.lit(severity).alias("severity"),
                    source_col.cast("string").alias("source_value"), target_col.cast("string").alias("e360_value"),
                    F.col("h.effective_date").alias("hr_effective_date"),
                    F.col("p.payroll_rows").alias("payroll_rows"), F.col("p.payroll_salaries").alias("payroll_salaries"),
                    (F.col(f"p.n_{field}") > 1 if owner == "Payroll" else F.lit(False)).alias("ambiguous")))
    d = reduce(lambda a, b: a.unionByName(b), diffs)

    future = F.col("hr_effective_date") > F.lit(snapshot_end).cast("date")
    reason = (
        F.when((F.col("field") == "effective_date") & future,
               F.lit("HR change is future-dated; Employee 360 correctly shows the value in force this month"))
        .when(F.col("payroll_rows").isNull() & (F.col("system_of_record") == "Payroll"),
              F.lit("No payroll record; the Employee 360 value has no source"))
        .when(F.col("ambiguous"),
              F.concat(F.lit("Payroll holds conflicting values ("), F.col("payroll_salaries"),
                       F.lit("); Employee 360 took the first, but the system of record is ambiguous")))
        .when(F.col("source_value").isNull(),
              F.lit("Blank in the system of record; the Employee 360 value cannot be traced to it"))
        .otherwise(F.lit("Employee 360 differs from the system of record")))
    classification = (F.when((F.col("field") == "effective_date") & future, "Legitimate exception")
                       .when(F.col("ambiguous"), "Cannot verify")
                       .otherwise("Error"))
    return (d.withColumn("classification", classification)
             .withColumn("reason", reason)
             .select("employee_id", "field", "system_of_record", "severity", "source_value", "e360_value",
                     "classification", "reason")
             .orderBy("classification", "severity", "employee_id"))


recon_fields = reconcile_fields(spark.table("stg_hr"), spark.table("stg_payroll"), spark.table("stg_e360"), SNAPSHOT_END)
RESULTS["recon_fields"] = recon_fields
display(recon_fields)

# COMMAND ----------

# MAGIC %md ## 4. Reconciliation summary

# COMMAND ----------

keys = spark.table("recon_keys")
summary = spark.createDataFrame([
    ("Employees in HR (system of record)", spark.table("stg_hr").count()),
    ("Rows in Employee 360", spark.table("stg_e360").count()),
    ("Matched on employee_id", keys.where("key_status = 'Matched'").count()),
    ("Missing downstream (in HR, not in Employee 360)", keys.where("key_status = 'Missing downstream'").count()),
    ("Unexpected downstream (in Employee 360, not in HR)", keys.where("key_status = 'Unexpected downstream'").count()),
    ("Matched employees with at least one field error", recon_fields.where("classification = 'Error'").select("employee_id").distinct().count()),
    ("Matched employees whose value cannot be verified (conflicting source)", recon_fields.where("classification = 'Cannot verify'").select("employee_id").distinct().count()),
    ("Field differences that are legitimate exceptions", recon_fields.where("classification = 'Legitimate exception'").count()),
], "measure string, value long")
RESULTS["recon_summary"] = summary
display(summary)

# COMMAND ----------

# MAGIC %md ## 5. Monitoring output
# MAGIC One row per rule. **Block release** = do not publish this Employee 360 build. **Alert now** =
# MAGIC notify the owner the same day; publishing may continue. **Monitor** = track the trend; alert only
# MAGIC above the threshold.

# COMMAND ----------

RULES = [
    # rule_id, rule, dimension, severity, action, alert when affected > , owner
    ("DQ01", "employee_id unique in every source",              "Uniqueness",            "Critical", "Block release", 0, "Payroll data owner"),
    ("DQ02", "Mandatory HR fields populated",                   "Completeness",          "Medium",   "Monitor",       1, "HR data steward"),
    ("DQ03", "manager_id exists in HR",                          "Referential integrity", "High",     "Alert now",     0, "HR data steward"),
    ("DQ04", "HR status agrees with payroll status",            "Consistency",           "Critical", "Alert now",     0, "Payroll and HR operations"),
    ("DQ05", "Payroll salary is a positive ZAR amount",         "Validity",              "High",     "Block release", 0, "Payroll data owner"),
    ("DQ06", "Record updated within 30 days of the extract",    "Freshness",             "Medium",   "Monitor",       2, "Source system owners"),
    ("RC01", "Every HR employee is in Employee 360",            "Reconciliation",        "Critical", "Block release", 0, "Employee 360 build team"),
    ("RC02", "No Employee 360 record without an HR employee",   "Reconciliation",        "Critical", "Block release", 0, "Employee 360 build team / MDM"),
    ("RC03", "Status, salary and currency match (and can be verified against) their source",  "Reconciliation",        "Critical", "Block release", 0, "Employee 360 build team"),
    ("RC04", "Department, manager, location and name match HR", "Reconciliation",        "High",     "Alert now",     0, "Employee 360 build team"),
]
rules = spark.createDataFrame(RULES, "rule_id string, rule string, dimension string, severity string, action string, "
                                     "alert_threshold int, owner string")

recon_failures = (
    keys.where("key_status <> 'Matched'")
        .select(F.when(F.col("key_status") == "Missing downstream", "RC01").otherwise("RC02").alias("rule_id"),
                "employee_id", F.lit("HR vs Employee 360").alias("source"), F.col("key_status").alias("detail"))
    .unionByName(
        recon_fields.where("classification <> 'Legitimate exception'")
        .select(F.when(F.col("severity") == "Critical", "RC03").otherwise("RC04").alias("rule_id"), "employee_id",
                F.lit("Source vs Employee 360").alias("source"),
                F.concat("field", F.lit(": "), F.coalesce("source_value", F.lit("blank")), F.lit(" -> "),
                         F.coalesce("e360_value", F.lit("blank")),
                         F.when(F.col("classification") == "Cannot verify",
                                F.lit(" (cannot verify: payroll holds conflicting values)")).otherwise(F.lit(""))
                         ).alias("detail"))))
failures = spark.table("dq_check_failures").unionByName(recon_failures)
RESULTS["failure_detail"] = failures.orderBy("rule_id", "employee_id")

agg = failures.groupBy("rule_id").agg(
    F.countDistinct("employee_id").alias("affected_count"),
    F.array_join(F.array_sort(F.collect_set("employee_id")), ", ").alias("affected_ids"))
monitoring = (rules.join(agg, "rule_id", "left")
    .withColumn("affected_count", F.coalesce("affected_count", F.lit(0)))
    .withColumn("status", F.when(F.col("affected_count") == 0, "PASS").otherwise("FAIL"))
    .withColumn("alert_fired", F.col("affected_count") > F.col("alert_threshold"))
    .withColumn("blocks_release", (F.col("action") == "Block release") & (F.col("affected_count") > 0))
    .select("rule_id", "rule", "dimension", "status", "affected_count", "severity", "action",
            F.concat(F.lit("> "), F.col("alert_threshold")).alias("alert_when_affected"), "alert_fired",
            "blocks_release", "owner", F.coalesce("affected_ids", F.lit("")).alias("affected_ids"))
    .orderBy("rule_id"))
RESULTS["monitoring"] = monitoring
display(monitoring)

release_blocked = monitoring.where("blocks_release").count() > 0
print(f"Release decision: {'BLOCK - do not publish this Employee 360 build' if release_blocked else 'OK to publish'}")

# COMMAND ----------

# MAGIC %md ## Save results (Databricks only)
# MAGIC Appends this run to Delta tables so trends and alert history survive between runs.

# COMMAND ----------

if ON_DATABRICKS:
    run_ts = F.current_timestamp()
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
    monitoring.withColumn("run_ts", run_ts).write.mode("append").saveAsTable(f"{TARGET_SCHEMA}.dq_monitoring")
    RESULTS["failure_detail"].withColumn("run_ts", run_ts).write.mode("append").saveAsTable(f"{TARGET_SCHEMA}.dq_failure_detail")
    print(f"appended to {TARGET_SCHEMA}.dq_monitoring and {TARGET_SCHEMA}.dq_failure_detail")

# COMMAND ----------

# In production the job runs with fail_on_block=true: the job fails here, after saving the results, so the
# task that publishes Employee 360 (which depends on this one) does not run.
if FAIL_ON_BLOCK and release_blocked:
    raise Exception("Blocking data-quality rule failed: " +
                    ", ".join(r["rule_id"] for r in monitoring.where("blocks_release").collect()))
