# Databricks notebook source
# MAGIC %md
# MAGIC # Exercise 2: incremental, restartable API ingestion (Delta Lake)
# MAGIC The same mock provider and the same rules as `exercise2-ingestion/ingest.py`, written to Delta tables.
# MAGIC
# MAGIC **What changes on Delta:** MySQL commits a page's rows, rejects and checkpoint in one transaction.
# MAGIC Delta commits one table at a time, so this version relies on *order plus idempotency* instead:
# MAGIC
# MAGIC 1. `MERGE` the page into `api_transactions` on `id`. A record is updated only if its `updated_at` moved forward.
# MAGIC 2. `MERGE` the rejects on a hash of the payload.
# MAGIC 3. Only then move the checkpoint (forward only).
# MAGIC 4. Update the run's counters.
# MAGIC
# MAGIC If the process dies anywhere, at most the last page is re-read next time. Re-applying it changes
# MAGIC nothing, because steps 1 and 2 are idempotent. The demo crashes on purpose between steps 2 and 3,
# MAGIC the worst place, and shows the result is still exact.
# MAGIC
# MAGIC **One run at a time:** in a Databricks Job, set *Maximum concurrent runs = 1*. That is Databricks'
# MAGIC equivalent of the MySQL version's `GET_LOCK`.

# COMMAND ----------

# MAGIC %run ./00_config

# COMMAND ----------

# MAGIC %md ## The mock provider (the supplied `mock_api.py`), running inside this notebook

# COMMAND ----------

__MOCK_API_SOURCE__


def start_mock_api(port, faults=True):
    """Run the supplied mock API on a background thread of this notebook's Python process."""
    global _MOCK_SERVER
    try:
        _MOCK_SERVER.shutdown()
        _MOCK_SERVER.server_close()
    except NameError:
        pass
    RECORDS.clear()
    RECORDS.update(build())                 # fresh provider data: 1,000 records
    STATE.update(requests=0, data_responses=0, faults=faults)
    _MOCK_SERVER = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=_MOCK_SERVER.serve_forever, daemon=True).start()
    print(f"mock API on http://127.0.0.1:{port} (faults {'on' if faults else 'off'})")


PORT = 8765
start_mock_api(PORT, faults=True)

# COMMAND ----------

# MAGIC %md ## Ingestion (the retry and validation code is copied unchanged from `ingest.py`)

# COMMAND ----------

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

API_BASE = f"http://127.0.0.1:{PORT}"
API_KEY = "test-key"          # the mock's documented key; in production from a Databricks secret scope
SOURCE = "mock_provider"
MAX_RETRIES = 6

__INGEST_HELPERS_SOURCE__


class SimulatedCrash(Exception):
    """Stands in for the process being killed (a node lost, a cancelled job)."""


def reset_tables():
    """Demo only: empty tables so the run can be repeated from scratch."""
    spark.sql("""CREATE OR REPLACE TABLE api_transactions (
        id STRING NOT NULL, player_id STRING NOT NULL, type STRING NOT NULL, amount DECIMAL(14,2) NOT NULL,
        currency STRING NOT NULL, status STRING NOT NULL, updated_at TIMESTAMP NOT NULL,
        source_system STRING NOT NULL, ingested_at TIMESTAMP NOT NULL) USING DELTA""")
    spark.sql("""CREATE OR REPLACE TABLE ingest_checkpoint (
        source_system STRING NOT NULL, next_cursor STRING, last_updated_at STRING, last_id STRING,
        updated_at TIMESTAMP) USING DELTA""")
    spark.sql("""CREATE OR REPLACE TABLE ingest_runs (
        run_id BIGINT NOT NULL, source_system STRING NOT NULL, started_at TIMESTAMP NOT NULL, finished_at TIMESTAMP,
        status STRING NOT NULL, pages_fetched INT, rows_new INT, rows_changed INT, rows_unchanged INT,
        rows_rejected INT, rate_limit_hits INT, server_error_hits INT, error_message STRING) USING DELTA""")
    spark.sql("""CREATE OR REPLACE TABLE ingest_rejects (
        payload_sha256 STRING NOT NULL, record_id STRING, reason STRING NOT NULL, raw_payload STRING NOT NULL,
        first_run_id BIGINT NOT NULL, last_seen_run_id BIGINT NOT NULL, rejected_at TIMESTAMP NOT NULL) USING DELTA""")


PAGE_SCHEMA = ("id STRING, player_id STRING, type STRING, amount DECIMAL(14,2), currency STRING, status STRING, "
               "updated_at TIMESTAMP, source_system STRING, ingested_at TIMESTAMP")


def run_once(page_limit=200, crash_after_page=None):
    # A run still RUNNING died without finishing (the Job allows one run at a time).
    abandoned = spark.sql("""UPDATE ingest_runs SET status = 'ABANDONED',
        error_message = 'process stopped without finishing; later runs resumed from the checkpoint'
        WHERE source_system = 'mock_provider' AND status = 'RUNNING'""").first()[0]
    if abandoned:
        print(f"marked {abandoned} earlier run(s) ABANDONED")
    run_id = (spark.sql("SELECT max(run_id) FROM ingest_runs").first()[0] or 0) + 1
    spark.sql(f"""INSERT INTO ingest_runs VALUES ({run_id}, '{SOURCE}', current_timestamp(), NULL, 'RUNNING',
                  0, 0, 0, 0, 0, 0, 0, NULL)""")
    cp = spark.sql(f"SELECT last_updated_at, last_id FROM ingest_checkpoint WHERE source_system = '{SOURCE}'").first()
    base = {"updated_since": cp[0], "limit": page_limit} if cp else {"limit": page_limit}
    print(f"=== run {run_id} " + (f"resuming from updated_since={cp[0]} (last id {cp[1]})" if cp else "full initial load"))

    stats = {"rate_hits": 0, "server_hits": 0}
    totals = dict(pages=0, new=0, changed=0, unchanged=0, rejected=0)
    cursor, status, error = None, "COMPLETED", None
    while True:
        body, err = api_get({"cursor": cursor, "limit": page_limit} if cursor else dict(base), stats)
        if err:
            status, error = "FAILED", err
            break
        page = list({r.get("id"): r for r in body["data"]}.values())       # collapse in-page repeats
        clean, rejects = [], []
        for rec in page:
            ok, reason = validate(rec)
            (clean.append(ok) if ok else rejects.append((rec, reason)))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [(c["id"], c["player_id"], c["type"], c["amount"], c["currency"], c["status"], c["updated_at"],
                 SOURCE, now) for c in clean]
        # 1. data: insert new ids; update only when updated_at moved forward (never overwrite newer data)
        spark.createDataFrame(rows, PAGE_SCHEMA).createOrReplaceTempView("page")
        m = spark.sql("""MERGE INTO api_transactions t USING page s ON t.id = s.id
                         WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
                         WHEN NOT MATCHED THEN INSERT *""").first()
        new, changed = int(m["num_inserted_rows"]), int(m["num_updated_rows"])
        # 2. rejects: once per distinct bad payload
        if rejects:
            rej = [(hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest(), rec.get("id"), reason,
                    json.dumps(rec), run_id, run_id, now) for rec, reason in rejects]
            spark.createDataFrame(rej, "payload_sha256 STRING, record_id STRING, reason STRING, raw_payload STRING, "
                                       "first_run_id BIGINT, last_seen_run_id BIGINT, rejected_at TIMESTAMP"
                                  ).createOrReplaceTempView("page_rejects")
            spark.sql("""MERGE INTO ingest_rejects t USING page_rejects s ON t.payload_sha256 = s.payload_sha256
                         WHEN MATCHED THEN UPDATE SET t.last_seen_run_id = s.last_seen_run_id
                         WHEN NOT MATCHED THEN INSERT *""")
        totals["pages"] += 1
        if crash_after_page == totals["pages"]:
            raise SimulatedCrash(f"killed after writing page {totals['pages']}, before its checkpoint")
        # 3. checkpoint: forward only
        if page:
            last = max(page, key=lambda r: (r["updated_at"], r["id"]))
            spark.createDataFrame([(SOURCE, body.get("next_cursor"), last["updated_at"], last["id"])],
                                  "source_system STRING, next_cursor STRING, last_updated_at STRING, last_id STRING"
                                  ).createOrReplaceTempView("new_checkpoint")
            spark.sql("""MERGE INTO ingest_checkpoint t USING new_checkpoint s ON t.source_system = s.source_system
                         WHEN MATCHED AND (s.last_updated_at > t.last_updated_at
                                           OR (s.last_updated_at = t.last_updated_at AND s.last_id >= t.last_id))
                           THEN UPDATE SET next_cursor = s.next_cursor, last_updated_at = s.last_updated_at,
                                           last_id = s.last_id, updated_at = current_timestamp()
                         WHEN NOT MATCHED THEN INSERT (source_system, next_cursor, last_updated_at, last_id, updated_at)
                           VALUES (s.source_system, s.next_cursor, s.last_updated_at, s.last_id, current_timestamp())""")
        # 4. run counters
        totals["new"] += new
        totals["changed"] += changed
        totals["unchanged"] += len(clean) - new - changed
        totals["rejected"] += len(rejects)
        spark.sql(f"""UPDATE ingest_runs SET pages_fetched = {totals['pages']}, rows_new = {totals['new']},
                      rows_changed = {totals['changed']}, rows_unchanged = {totals['unchanged']},
                      rows_rejected = {totals['rejected']}, rate_limit_hits = {stats['rate_hits']},
                      server_error_hits = {stats['server_hits']} WHERE run_id = {run_id}""")
        print(f"  page {totals['pages']}: {new} new, {changed} changed, {len(clean) - new - changed} unchanged, "
              f"{len(rejects)} rejected, has_more={body.get('has_more')}")
        if not body.get("has_more"):
            break
        cursor = body.get("next_cursor")
    msg = "NULL" if error is None else "'" + error.replace("'", "''") + "'"
    spark.sql(f"""UPDATE ingest_runs SET finished_at = current_timestamp(), status = '{status}',
                  rate_limit_hits = {stats['rate_hits']}, server_error_hits = {stats['server_hits']},
                  error_message = {msg} WHERE run_id = {run_id}""")
    print(f"=== run {run_id} {status}: {totals['new']} new, {totals['changed']} changed, "
          f"{totals['unchanged']} unchanged, {totals['rejected']} rejected "
          f"(429s: {stats['rate_hits']}, 500s: {stats['server_hits']})")
    return status


def verify_against_api():
    """Every id at the provider must be loaded (latest version) or quarantined; no duplicates."""
    stats, api, cursor = {"rate_hits": 0, "server_hits": 0}, {}, None
    while True:
        body, err = api_get({"cursor": cursor, "limit": 200} if cursor else {"limit": 200}, stats)
        assert not err, err
        api.update({r["id"]: r for r in body["data"]})
        if not body.get("has_more"):
            break
        cursor = body["next_cursor"]
    table = {r["id"]: r["updated_at"] for r in spark.table("api_transactions").select("id", "updated_at").collect()}
    rejected = {r[0] for r in spark.sql("SELECT DISTINCT record_id FROM ingest_rejects WHERE record_id IS NOT NULL").collect()}
    dupes = spark.sql("SELECT COUNT(*) - COUNT(DISTINCT id) FROM api_transactions").first()[0]
    api_time = {i: datetime.strptime(r["updated_at"], "%Y-%m-%dT%H:%M:%SZ") for i, r in api.items()}
    missing = sorted(set(api) - set(table) - rejected)
    stale = sorted(i for i in set(api) & set(table) if table[i] < api_time[i])
    unexpected = sorted(set(table) - set(api))
    quarantined = sorted(rejected & (set(api) - set(table)))
    print(f"API ids {len(api):,} = loaded {len(table):,} + quarantined {len(quarantined)} {quarantined}; "
          f"missing {len(missing)}, stale {len(stale)}, unexpected {len(unexpected)}, duplicates {dupes}")
    check(not (missing or stale or unexpected or dupes), "the table matches the API exactly")

# COMMAND ----------

# MAGIC %md ## Demo: crash, restart, rerun, new activity, rerun

# COMMAND ----------

reset_tables()
print("Run 1: 50-record pages; the process dies after writing page 2's data, before its checkpoint")
try:
    run_once(page_limit=50, crash_after_page=2)
except SimulatedCrash as e:
    print("  >>> " + str(e))
display(spark.sql("""SELECT (SELECT COUNT(*) FROM api_transactions) AS rows_loaded,
                            (SELECT COUNT(DISTINCT id) FROM api_transactions) AS distinct_ids,
                            (SELECT last_id FROM ingest_checkpoint) AS checkpoint_last_id,
                            (SELECT status FROM ingest_runs WHERE run_id = 1) AS run_1_status"""))

# COMMAND ----------

print("Run 2: restart. Page 2 is re-read (its rows are already there, so they count as unchanged).")
run_once()
verify_against_api()

# COMMAND ----------

print("Run 3: run again straight away, with nothing new at the provider")
run_once()

# COMMAND ----------

print("Interviewer step: POST /admin/advance")
req = urllib.request.Request(f"{API_BASE}/admin/advance", method="POST", data=b"")
print(json.loads(urllib.request.urlopen(req, timeout=5).read()))
print("Run 4: loads only the new and changed records")
run_once()
verify_against_api()

# COMMAND ----------

# MAGIC %md ## Monitoring: run history, rejects, last successful position

# COMMAND ----------

display(spark.sql("""SELECT run_id, status, pages_fetched, rows_new, rows_changed, rows_unchanged, rows_rejected,
                            rate_limit_hits, server_error_hits,
                            timestampdiff(SECOND, started_at, finished_at) AS seconds, error_message
                     FROM ingest_runs ORDER BY run_id"""))
display(spark.sql("SELECT record_id, reason, first_run_id, last_seen_run_id FROM ingest_rejects"))
display(spark.table("ingest_checkpoint"))

runs = {r["run_id"]: r for r in spark.table("ingest_runs").collect()}
check(runs[1]["status"] == "ABANDONED", "the crashed run is marked ABANDONED")
check(runs[3]["rows_new"] == 0 and runs[3]["rows_changed"] == 0, "a rerun with nothing new loads nothing")
check(runs[4]["rows_new"] == 25 and runs[4]["rows_changed"] == 40, "after new activity: exactly 25 new and 40 changed")
check(spark.table("ingest_rejects").count() == 1, "the bad record (TX000777) is quarantined once")
