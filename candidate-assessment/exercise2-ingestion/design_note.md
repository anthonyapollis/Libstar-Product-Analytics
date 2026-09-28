# Exercise 2: design note

**Database:** MySQL 8 / MariaDB (the brief allows any; the same server holds the other exercises
and dbt). **Program:** `ingest.py`, Python standard library plus `pymysql`.

**Tracking progress.**
- A checkpoint table holds the last `(updated_at, id)` the load has fully committed.
- Each run resumes with `updated_since` = that `updated_at` (inclusive, per the API doc), then pages
  with the server's cursor.
- The API moves a record's `updated_at` forward when it changes, so one position covers both new
  and changed records.
- Each run logs pages, new / changed / unchanged / rejected counts, 429 and 500 counts, start and
  end times, and a status (`ingest_runs`).

**Avoiding duplicates.**
- `id` is the primary key, and every write is an upsert on it.
- Repeated rows within a page are collapsed before writing.
- A record is written only if it's new or its `updated_at` moved forward, so an older version never
  overwrites a newer one.
- **One transaction per page:** the page's rows, its rejects, the checkpoint and the run counters
  commit together. A kill at any moment loses at most the uncommitted page, which the next run
  re-reads.

**Handling failures.**
- **Rate limiting (429):** wait for `Retry-After`, then retry.
- **Server and network errors:** retry with 2, 4, 8… s backoff (6 attempts), then end the run as
  FAILED with exit code 1. The checkpoint is unchanged, so the next run carries on.
- **Bad records:** numbers sent as strings are coerced. Records that can't be used (missing
  `player_id`, unparseable amount or time, negative amount) go to `ingest_rejects` with the reason
  and the raw JSON, once per distinct payload. The run continues.
- **Overlapping runs:** a database lock (`GET_LOCK`) lets only one run proceed. A run killed
  mid-way is marked ABANDONED by the next one.

**Evidence.** `demo.py` hard-kills a run mid-page, restarts it, runs the interviewer's
`/admin/advance`, reruns, and checks every id against the API: 1,025 = 1,024 loaded + 1
quarantined, with 0 missing, 0 stale and 0 duplicates.

**For production.**
- **Scheduling:** a scheduler such as Airflow or cron every few minutes. The lock makes overlaps
  harmless.
- **Alerting:** alert on exit code ≠ 0, on a run stuck RUNNING past one interval, on a rising
  reject rate, and on checkpoint lag.
- **Secrets:** API key and database password from a secrets manager (they're already read from
  environment variables).
- **Scale:** bulk-load each page into a staging table and `MERGE`; partition by date; split id
  ranges across workers if the rate limit becomes the bottleneck.
