# Databricks notebook source
# MAGIC %md
# MAGIC # JSB assessment on Databricks: configuration
# MAGIC Every other notebook starts with `%run ./00_config`. Change the catalog or schema here only.
# MAGIC
# MAGIC * **Catalog:** Databricks Free Edition has a catalog called `workspace`.
# MAGIC * **Schema:** everything is created in the `jsb_assessment` schema inside that catalog.
# MAGIC * **Conventions:** times are UTC and amounts are NAD, as the brief states.

# COMMAND ----------

CATALOG = "workspace"          # Unity Catalog catalog (Free Edition default)
SCHEMA = "jsb_assessment"      # all tables for the three exercises

try:
    dbutils  # noqa: F821  (exists on Databricks only)
    ON_DATABRICKS = True
except NameError:
    ON_DATABRICKS = False      # local test run (open-source Spark + Delta Lake)

if ON_DATABRICKS:
    spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
spark.sql(f"USE {SCHEMA}")
spark.conf.set("spark.sql.session.timeZone", "UTC")

try:
    display  # noqa: B018  (Databricks notebook built-in)
except NameError:
    def display(df, n=60):
        df.show(n, truncate=False)


def check(condition, message):
    """Fail the notebook loudly if a result is not what the MySQL/dbt build produced."""
    if not condition:
        raise AssertionError("CHECK FAILED: " + message)
    print("PASS: " + message)


print(f"Using {CATALOG + '.' if ON_DATABRICKS else ''}{SCHEMA} (Databricks: {ON_DATABRICKS})")
