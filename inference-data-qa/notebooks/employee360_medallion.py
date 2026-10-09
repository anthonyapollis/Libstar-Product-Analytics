# Databricks notebook source
# MAGIC %md
# MAGIC # Employee 360 pipeline: Bronze → Silver → Gold
# MAGIC | Layer | Tables | What it holds |
# MAGIC |---|---|---|
# MAGIC | **Bronze** | `bronze_hr`, `bronze_payroll`, `bronze_e360`, `ingest_batches` | Every delivered row, as strings, with the batch it arrived in. Loaded incrementally (`employee360_incremental`). |
# MAGIC | **Silver** | `silver_hr`, `silver_payroll`, `silver_e360_delivered` | The current delivery, typed and standardised. The data-quality checks run on these definitions. |
# MAGIC | **Gold** | `gold_employee_360`, `gold_dq_monitoring`, `dq_issues` | A trusted Employee 360 rebuilt by the ownership rules with each employee's open rules, the monitoring history and the issue lifecycle. |
# MAGIC
# MAGIC Run it on a schedule. If no extract changed, the incremental step stops the run before Silver and Gold
# MAGIC are rebuilt, so nothing is recomputed.

# COMMAND ----------

# MAGIC %run ./employee360_incremental

# COMMAND ----------

# Silver and Gold, from the same definitions the checks used.
RESULTS["failure_detail"].createOrReplaceTempView("dq_failure_detail_v")
PARAMS["schema"] = TARGET_SCHEMA
run_sql_file("10_silver_gold.sql", keep=["gold_vs_delivered"])

# Monitoring history in Gold: one row per rule per run.
(RESULTS["monitoring"].withColumn("run_id", F.lit(RUN_ID)).withColumn("run_at", F.current_timestamp())
    .write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(f"{TARGET_SCHEMA}.gold_dq_monitoring"))

gold = spark.table(f"{TARGET_SCHEMA}.gold_employee_360")
RESULTS["gold_employee_360"] = gold.drop("gold_built_at").orderBy("employee_id")
print("Gold records that are not trusted, and why:")
display(gold.where("NOT is_trusted").select("employee_id", "employment_status", "payroll_status",
                                            "monthly_salary_zar", "dq_rules_failed").orderBy("employee_id"))

# COMMAND ----------

layers = spark.createDataFrame(
    [(layer, t, spark.table(f"{TARGET_SCHEMA}.{t}").count()) for layer, t in [
        ("Bronze", "bronze_hr"), ("Bronze", "bronze_payroll"), ("Bronze", "bronze_e360"),
        ("Silver", "silver_hr"), ("Silver", "silver_payroll"), ("Silver", "silver_e360_delivered"),
        ("Gold", "gold_employee_360"), ("Gold", "gold_dq_monitoring"), ("Gold", "dq_issues")]],
    "layer string, table_name string, row_count long")
RESULTS["layers"] = layers
display(layers)
