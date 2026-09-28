"""Check the loaded table against the provider's API, record by record.

Reads every record from the API (cursor paging from the start, with the same retry logic as
ingest.py), then checks the database:
  * missing:    ids the API has that are neither in `transactions` nor quarantined in `ingest_rejects`
  * unexpected: ids in `transactions` the API doesn't have
  * stale:      ids whose stored updated_at is older than the API's (a change not loaded)
  * duplicates: `transactions` rows sharing an id (impossible with the primary key, checked anyway)
Exits 0 when all four are zero, 1 otherwise. Uses the same DB_* / INGEST_* settings as ingest.py.
Usage: python verify_against_api.py
"""
import sys
from datetime import datetime

import pymysql

import ingest


def api_snapshot():
    stats = {"rate_hits": 0, "server_hits": 0}
    records, cursor = {}, None
    while True:
        params = {"cursor": cursor, "limit": 200} if cursor else {"limit": 200}
        body, err = ingest.api_get(params, stats)
        if err:
            sys.exit(f"could not read the API: {err}")
        for rec in body["data"]:
            records[rec["id"]] = rec          # in-page repeats collapse onto one id
        if not body.get("has_more"):
            return records
        cursor = body["next_cursor"]


def main():
    api = api_snapshot()
    conn = pymysql.connect(**dict(ingest.DB, autocommit=True))
    cur = conn.cursor()
    cur.execute("SELECT id, updated_at FROM transactions")
    table = dict(cur.fetchall())
    cur.execute("SELECT COUNT(*) - COUNT(DISTINCT id) FROM transactions")
    duplicates = cur.fetchone()[0]
    cur.execute("SELECT DISTINCT record_id FROM ingest_rejects WHERE record_id IS NOT NULL")
    rejected = {r[0] for r in cur.fetchall()}
    conn.close()

    api_time = {i: datetime.strptime(r["updated_at"], "%Y-%m-%dT%H:%M:%SZ") for i, r in api.items()}
    missing = sorted(set(api) - set(table) - rejected)
    unexpected = sorted(set(table) - set(api))
    stale = sorted(i for i in set(api) & set(table) if table[i] < api_time[i])
    quarantined = sorted(rejected & (set(api) - set(table)))

    print(f"API records (unique ids):      {len(api):,}")
    print(f"loaded in transactions:        {len(table):,}")
    print(f"quarantined in ingest_rejects: {len(quarantined):,} {quarantined}")
    print(f"accounted for (loaded + quarantined): {len(set(table) | set(quarantined)):,}")
    print(f"missing: {len(missing)} {missing[:10]}")
    print(f"unexpected: {len(unexpected)} {unexpected[:10]}")
    print(f"stale (change not loaded): {len(stale)} {stale[:10]}")
    print(f"duplicate rows: {duplicates}")
    ok = not (missing or unexpected or stale or duplicates)
    print("VERIFIED: the table matches the API exactly" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
