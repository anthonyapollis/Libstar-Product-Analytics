"""Show incremental loading end to end: API -> ingest.py -> dbt incremental model.

  1. start the mock API; reset the 4 Exercise 2 tables in jsb_assessment
  2. ingest.py: full initial load (999 loaded, 1 quarantined)
  3. dbt run --full-refresh fct_api_transactions: builds the mart (999 rows)
  4. dbt run again: 0 rows, because nothing changed
  5. POST /admin/advance, then ingest.py: 25 new + 40 changed records
  6. dbt run (incremental): exactly those 65 rows are merged; the mart then equals the source
Output goes to evidence/incremental_run.txt. Afterwards, re-run exercise2-ingestion/demo.py
--database jsb_assessment to restore the submission's Exercise 2 data (4 runs, one killed).

Settings: DB_* as for ingest.py, plus DBT_PROFILES_DIR and DBT_TARGET (default dev).
Usage: python incremental_demo.py
"""
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
EX2 = HERE.parent / "exercise2-ingestion"
PORT = 8766
LOG = []


def say(text=""):
    print(text, flush=True)
    LOG.append(text)


def sh(args, cwd, env, grep=None):
    out = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True).stdout
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    for line in out.splitlines():
        if grep is None or re.search(grep, line):
            say("  | " + line)
    return out


def scalar(sql):
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
        unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
        password=os.environ.get("DB_PASSWORD", "AssessPass123!"), autocommit=True)
    cur = conn.cursor()
    cur.execute(sql)
    value = cur.fetchone()[0]
    conn.close()
    return value.decode() if isinstance(value, bytes) else value


def main():
    env = dict(os.environ, DB_NAME="jsb_assessment", INGEST_API_BASE=f"http://127.0.0.1:{PORT}",
               DBT_PROFILES_DIR=os.environ.get("DBT_PROFILES_DIR", str(HERE)))
    target = ["--target", os.environ.get("DBT_TARGET", "dev")]
    dbt = [str(Path(sys.executable).parent / "dbt")]
    dbt_run = dbt + ["run", "--select", "fct_api_transactions"] + target
    counts = ("SELECT CONCAT((SELECT COUNT(*) FROM jsb_assessment.transactions), ' source rows / ', "
              "(SELECT COUNT(*) FROM jsb_platform_marts.fct_api_transactions), ' mart rows')")

    api = subprocess.Popen([sys.executable, "mock_api.py", "--port", str(PORT), "--no-faults"], cwd=EX2,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        say("1. Reset the Exercise 2 tables and run the initial load")
        schema = (EX2 / "schema.sql").read_text(encoding="utf-8")
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
            unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
            password=os.environ.get("DB_PASSWORD", "AssessPass123!"), autocommit=True)
        for stmt in [s.strip() for s in re.sub(r"--[^\n]*", "", schema).split(";") if s.strip()]:
            conn.cursor().execute(stmt)
        conn.close()
        sh([sys.executable, "ingest.py"], EX2, env, grep=r"COMPLETED")

        say("\n2. dbt run --full-refresh: build the mart from scratch")
        sh(dbt_run + ["--full-refresh"], HERE, env, grep=r"OK created")
        say(f"  {scalar(counts)}")

        say("\n3. dbt run again with nothing new: the incremental filter selects nothing")
        sh(dbt_run, HERE, env, grep=r"OK created")

        say("\n4. New activity at the provider, then ingest.py")
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/admin/advance", method="POST",
                                                      data=b""), timeout=5)
        sh([sys.executable, "ingest.py"], EX2, env, grep=r"COMPLETED")

        say("\n5. dbt run (incremental): only the new and changed rows are merged")
        sh(dbt_run, HERE, env, grep=r"OK created")
        say(f"  {scalar(counts)}")
        stale = scalar("SELECT COUNT(*) FROM jsb_assessment.transactions t "
                       "LEFT JOIN jsb_platform_marts.fct_api_transactions m ON m.id = t.id "
                       "WHERE m.id IS NULL OR m.updated_at <> t.updated_at OR m.status <> t.status "
                       "OR m.amount <> t.amount")
        dupes = scalar("SELECT COUNT(*) - COUNT(DISTINCT id) FROM jsb_platform_marts.fct_api_transactions")
        say(f"  rows in the source that the mart is missing or has an old version of: {stale}")
        say(f"  duplicate ids in the mart: {dupes}")
        sh(dbt + ["test", "--select", "fct_api_transactions"] + target, HERE, env, grep=r"PASS|FAIL|Done")
        say("\nRESULT: " + ("PASS" if stale == 0 and dupes == 0 else "FAIL"))
    finally:
        api.terminate()
        (HERE / "evidence" / "incremental_run.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
