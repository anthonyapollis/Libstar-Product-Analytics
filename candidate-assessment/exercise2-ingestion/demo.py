"""Reproduce the Exercise 2 evidence end to end, on any OS, into its own database.

  1. start the mock API (faults ON: 429s, 500s and repeated rows are all live)
  2. create a fresh schema in the demo database (default jsb_ingest_demo)
  3. run 1: small pages and a pause before each commit; hard-kill it mid-page
  4. show the table, checkpoint and run log right after the kill
  5. run 2: restart normally; it resumes from the checkpoint and finishes
  6. check every record against the API (verify_against_api.py)
  7. run 3: run again straight away: nothing new, nothing changed
  8. POST /admin/advance (the interviewer's "new activity" step)
  9. run 4: loads only the new and changed records; check against the API again
Everything printed is also written to evidence/run_transcript.txt.

Database settings: DB_HOST, DB_PORT, DB_SOCKET, DB_USER, DB_PASSWORD, as for ingest.py.
Usage: python demo.py [--database jsb_ingest_demo] [--port 8765]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
LOG = []


def say(text=""):
    print(text, flush=True)
    LOG.append(text)


def heading(text):
    say()
    say("=" * 78)
    say(text)
    say("=" * 78)


def db_conn(database=None):
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
        unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
        password=os.environ.get("DB_PASSWORD", "AssessPass123!"), database=database, autocommit=True)


def query(database, sql):
    conn = db_conn(database)
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    conn.close()
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c)) for i, c in enumerate(cols)]
    say("  " + "  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        say("  " + "  ".join(("" if v is None else str(v)).ljust(w) for v, w in zip(r, widths)))


def run(cmd, env, kill_after=None):
    """Run a child process, echo its output; with kill_after, hard-kill it when that line appears
    for the second time (i.e. page 1 is committed and page 2 is fetched but not yet committed)."""
    proc = subprocess.Popen([sys.executable, "-u", *cmd], cwd=HERE, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    seen = 0
    for line in proc.stdout:
        say("  | " + line.rstrip())
        if kill_after and kill_after in line:
            seen += 1
            if seen == 2:
                proc.kill()          # TerminateProcess on Windows, SIGKILL elsewhere: no clean-up runs
                proc.wait()
                say("  >>> process hard-killed mid-page (page 2 fetched, not committed)")
                return -9
    return proc.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", default="jsb_ingest_demo")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    db, base = args.database, f"http://127.0.0.1:{args.port}"
    env = dict(os.environ, DB_NAME=db, INGEST_API_BASE=base, PYTHONIOENCODING="utf-8")

    heading(f"1. Start the mock API on port {args.port} (faults on)")
    api = subprocess.Popen([sys.executable, "mock_api.py", "--port", str(args.port)], cwd=HERE,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{base}/v1/transactions?limit=1", timeout=1)
                break
            except urllib.error.HTTPError:
                break                            # any HTTP answer (even 401) means it is up
            except OSError:
                time.sleep(0.2)
        say("  mock API is up")

        heading(f"2. Fresh schema in database `{db}`")
        conn = db_conn()
        conn.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{db}`")
        conn.close()
        conn = db_conn(db)
        schema = (HERE / "schema.sql").read_text(encoding="utf-8").replace("USE jsb_assessment;", "")
        for stmt in [s.strip() for s in re.sub(r"--[^\n]*", "", schema).split(";")]:
            if stmt:
                conn.cursor().execute(stmt)
        conn.close()
        say("  created transactions, ingest_checkpoint, ingest_runs, ingest_rejects")

        heading("3. Run 1: 50-record pages, 2 s pause before each commit; kill it mid-page")
        run(["ingest.py"], dict(env, INGEST_PAGE_LIMIT="50", INGEST_DEMO_DELAY="2"),
            kill_after="[demo] sleeping")

        heading("4. State right after the kill: only page 1 is in the table")
        query(db, "SELECT COUNT(*) AS rows_loaded, COUNT(DISTINCT id) AS distinct_ids FROM transactions")
        query(db, "SELECT last_updated_at, last_id FROM ingest_checkpoint")
        query(db, "SELECT run_id, status, pages_fetched, rows_new FROM ingest_runs")

        heading("5. Run 2: restart with normal settings; resumes from the checkpoint")
        run(["ingest.py"], env)
        query(db, "SELECT COUNT(*) AS rows_loaded, COUNT(DISTINCT id) AS distinct_ids FROM transactions")
        query(db, "SELECT record_id, reason, run_id, last_seen_run_id FROM ingest_rejects")
        query(db, "SELECT id, amount FROM transactions WHERE id = 'TX000500'")

        heading("6. Check every record against the API")
        rc1 = run(["verify_against_api.py"], env)

        heading("7. Run 3: run again straight away (nothing has changed at the provider)")
        run(["ingest.py"], env)

        heading("8. Interviewer step: POST /admin/advance (new activity at the provider)")
        req = urllib.request.Request(f"{base}/admin/advance", method="POST", data=b"")
        say("  " + json.dumps(json.loads(urllib.request.urlopen(req, timeout=5).read())))

        heading("9. Run 4: loads only the new and changed records")
        run(["ingest.py"], env)
        rc2 = run(["verify_against_api.py"], env)

        heading("10. Final state")
        query(db, "SELECT COUNT(*) AS rows_loaded, COUNT(DISTINCT id) AS distinct_ids, "
                  "COUNT(*) - COUNT(DISTINCT id) AS duplicates FROM transactions")
        query(db, "SELECT run_id, status, pages_fetched, rows_new, rows_changed, rows_unchanged, "
                  "rows_rejected, rate_limit_hits, server_error_hits, "
                  "TIMESTAMPDIFF(SECOND, started_at, finished_at) AS seconds FROM ingest_runs ORDER BY run_id")
        query(db, "SELECT last_updated_at, last_id FROM ingest_checkpoint")
        ok = rc1 == 0 and rc2 == 0
        say()
        say("RESULT: " + ("PASS: after a hard kill, a restart and new provider activity, the table matches the API "
                          "exactly: no duplicates, nothing missing, every change loaded, bad record quarantined."
                          if ok else "FAIL: see the verification output above"))
    finally:
        api.terminate()
        (HERE / "evidence" / "run_transcript.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
