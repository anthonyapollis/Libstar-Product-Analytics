"""Incremental, restartable ingestion of the mock transactions API into MySQL.

Usage:
    python mock_api.py                 # in one terminal
    python ingest.py                   # in another, run repeatedly / on a schedule

Design summary (full detail in design_note.md):
  * Progress is tracked in MySQL (`ingest_checkpoint`), not in memory or a local
    file, so any process on any host can resume it.
  * Each page of records is upserted (INSERT ... ON DUPLICATE KEY UPDATE, keyed
    on the provider's `id`) and the checkpoint is advanced IN THE SAME
    transaction, committed together. A kill at any point -- mid-page, between
    pages, between runs -- leaves the table and the checkpoint consistent with
    each other, so re-running never duplicates and never skips.
  * A run always resumes from `updated_since = last processed updated_at`
    (inclusive), then paginates within the run using the server's cursor
    (which takes precedence over updated_since per the API doc). This means a
    run never needs to persist a live cursor across a restart -- only a
    completed page's checkpoint matters -- which is what keeps "kill at any
    moment" simple to reason about. The one cost: the boundary row from the
    last completed page is re-fetched and re-upserted next run. That is a
    no-op (idempotent) by design, not a duplicate.
  * Bad records (unparseable amount, missing player_id) are quarantined to
    `ingest_rejects` with the raw payload and a reason -- never silently
    dropped -- and do not stop the run.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import pymysql

API_BASE = "http://127.0.0.1:8000"
API_KEY = "test-key"
SOURCE = "mock_provider"
PAGE_LIMIT = int(os.environ.get("INGEST_PAGE_LIMIT", 200))
MAX_RETRIES = 6
# Demo-only: sleep after fetching a page but before committing it, so a kill
# during the sleep proves an in-flight (uncommitted) page is safely discarded.
# Not used in normal operation (defaults to 0).
DEMO_DELAY = float(os.environ.get("INGEST_DEMO_DELAY", 0))

DB = dict(host="127.0.0.1", user="assess", password="AssessPass123!",
          database="jsb_assessment", autocommit=False)


def api_get(params, stats):
    """GET /v1/transactions with retry on 429 (Retry-After) and 500 (backoff).
    `stats` is a mutable dict this call increments in place (rate_hits, server_hits)."""
    url = f"{API_BASE}/v1/transactions?{urlencode(params)}"
    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    attempt = 0
    while True:
        attempt += 1
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read()), None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                stats["rate_hits"] += 1
                wait = float(e.headers.get("Retry-After", "1"))
                print(f"  [429 rate limited] sleeping {wait}s (attempt {attempt})")
                time.sleep(wait)
            elif e.code == 500:
                stats["server_hits"] += 1
                wait = min(2 ** attempt, 30)
                print(f"  [500 server error] backing off {wait}s (attempt {attempt})")
                time.sleep(wait)
            else:
                raise
            if attempt >= MAX_RETRIES:
                return None, f"http_{e.code}_retries_exhausted"
        except urllib.error.URLError as e:
            wait = min(2 ** attempt, 30)
            print(f"  [network error: {e}] backing off {wait}s (attempt {attempt})")
            time.sleep(wait)
            if attempt >= MAX_RETRIES:
                return None, "network_error_exhausted"


def validate(rec):
    """Coerce/validate one raw record. Returns (clean_dict, None) or (None, reason)."""
    if not rec.get("player_id"):
        return None, "missing player_id"
    try:
        amount = Decimal(str(rec["amount"])).quantize(Decimal("0.01"))
    except (InvalidOperation, KeyError, TypeError):
        return None, f"unparseable amount: {rec.get('amount')!r}"
    if amount < 0:
        return None, f"negative amount: {amount}"
    try:
        updated_at = datetime.strptime(rec["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
    except (KeyError, ValueError):
        return None, f"unparseable updated_at: {rec.get('updated_at')!r}"
    if not rec.get("id") or not rec.get("type") or not rec.get("status"):
        return None, "missing required field (id/type/status)"
    return {
        "id": rec["id"], "player_id": rec["player_id"], "type": rec["type"],
        "amount": amount, "currency": rec.get("currency", "NAD"),
        "status": rec["status"], "updated_at": updated_at,
    }, None


def get_checkpoint(cur):
    cur.execute("SELECT last_updated_at, last_id FROM ingest_checkpoint WHERE source_system=%s", (SOURCE,))
    row = cur.fetchone()
    return row if row else (None, None)


def start_run(cur):
    cur.execute(
        "INSERT INTO ingest_runs (source_system, started_at, status) VALUES (%s, %s, 'RUNNING')",
        (SOURCE, datetime.now(timezone.utc)),
    )
    return cur.lastrowid


def run_once():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    run_id = start_run(cur)
    conn.commit()
    print(f"=== run {run_id} starting ===")

    last_updated_at, last_id = get_checkpoint(cur)
    if last_updated_at:
        print(f"resuming from updated_since={last_updated_at} (last id seen: {last_id})")
        base_params = {"updated_since": last_updated_at, "limit": PAGE_LIMIT}
    else:
        print("no checkpoint found: full initial load")
        base_params = {"limit": PAGE_LIMIT}

    cursor = None
    pages = upserted = rejected = 0
    stats = {"rate_hits": 0, "server_hits": 0}
    status = "COMPLETED"
    error_message = None

    try:
        while True:
            params = {"cursor": cursor, "limit": PAGE_LIMIT} if cursor else dict(base_params)

            body, err = api_get(params, stats)
            if err:
                status, error_message = "FAILED", err
                break

            data = body["data"]
            # Dedupe within-page repeats (server occasionally echoes a row twice);
            # last occurrence wins, order preserved by insertion.
            deduped = {}
            for rec in data:
                deduped[rec.get("id")] = rec
            page_records = list(deduped.values())

            clean_rows, reject_rows = [], []
            for rec in page_records:
                clean, reason = validate(rec)
                if clean:
                    clean_rows.append(clean)
                else:
                    reject_rows.append((rec.get("id"), reason, json.dumps(rec)))

            # Atomic unit: data + rejects + checkpoint + run counters, or nothing.
            if clean_rows:
                cur.executemany(
                    """INSERT INTO transactions (id, player_id, type, amount, currency, status, updated_at, source_system)
                       VALUES (%(id)s, %(player_id)s, %(type)s, %(amount)s, %(currency)s, %(status)s, %(updated_at)s, %(source)s)
                       ON DUPLICATE KEY UPDATE
                         player_id=VALUES(player_id), type=VALUES(type), amount=VALUES(amount),
                         currency=VALUES(currency), status=VALUES(status), updated_at=VALUES(updated_at)""",
                    [dict(c, source=SOURCE) for c in clean_rows],
                )
            if reject_rows:
                cur.executemany(
                    "INSERT INTO ingest_rejects (run_id, record_id, reason, raw_payload) VALUES (%s,%s,%s,%s)",
                    [(run_id, rid, reason, payload) for rid, reason, payload in reject_rows],
                )

            if page_records:
                last_rec = sorted(page_records, key=lambda r: (r["updated_at"], r["id"]))[-1]
                cur.execute(
                    """INSERT INTO ingest_checkpoint (source_system, next_cursor, last_updated_at, last_id)
                       VALUES (%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE next_cursor=VALUES(next_cursor),
                         last_updated_at=VALUES(last_updated_at), last_id=VALUES(last_id)""",
                    (SOURCE, body.get("next_cursor"), last_rec["updated_at"], last_rec["id"]),
                )

            if DEMO_DELAY:
                print(f"  [demo] sleeping {DEMO_DELAY}s before commit (kill now to test safety)")
                time.sleep(DEMO_DELAY)

            pages += 1
            upserted += len(clean_rows)
            rejected += len(reject_rows)
            cur.execute(
                """UPDATE ingest_runs SET pages_fetched=%s, rows_upserted=%s, rows_rejected=%s,
                   rate_limit_hits=%s, server_error_hits=%s, final_cursor=%s WHERE run_id=%s""",
                (pages, upserted, rejected, stats["rate_hits"], stats["server_hits"],
                 body.get("next_cursor"), run_id),
            )
            conn.commit()  # <-- the whole page's work becomes durable here, atomically
            print(f"  page {pages}: {len(clean_rows)} upserted, {len(reject_rows)} rejected, "
                  f"has_more={body.get('has_more')}")

            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")

    except KeyboardInterrupt:
        # Best-effort bookkeeping only. Safety comes from per-page commits above,
        # not from catching this -- a SIGKILL or crash skips this block entirely
        # and the table is still left correct because nothing partial was committed.
        status, error_message = "INTERRUPTED", "killed by operator"
        conn.rollback()
        print("  [interrupted] rolling back the in-flight page (already-committed pages are safe)")
    except Exception as e:  # noqa: BLE001 - top-level run guard, logged to ingest_runs
        conn.rollback()
        status, error_message = "FAILED", str(e)

    cur.execute(
        "UPDATE ingest_runs SET finished_at=%s, status=%s, rate_limit_hits=%s, server_error_hits=%s, error_message=%s WHERE run_id=%s",
        (datetime.now(timezone.utc), status, stats["rate_hits"], stats["server_hits"], error_message, run_id),
    )
    conn.commit()
    print(f"=== run {run_id} {status}: {pages} pages, {upserted} upserted, {rejected} rejected "
          f"(429s: {stats['rate_hits']}, 500s: {stats['server_hits']}) ===")
    conn.close()
    return status


if __name__ == "__main__":
    run_once()
