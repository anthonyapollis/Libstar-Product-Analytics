# Exercise 2 — Design note

**Tools used:** Python 3 (standard library `urllib` only, no extra HTTP deps), MySQL 8.0, Postman
(collection in `postman/`) for exploring and documenting the API contract.

## How progress is tracked
A single-row-per-source checkpoint in MySQL (`ingest_checkpoint`: `last_updated_at`, `last_id`), not
memory or a local file, so any process on any host can resume it. Each run resumes with
`updated_since = last_updated_at` (inclusive) and then paginates *within* that run using the server's
`cursor`, which the API doc says takes precedence over `updated_since`. A run never has to persist a
live cursor across a process restart — only a fully committed page's checkpoint matters — which is what
keeps "safe to kill at any moment" simple to reason about, at the cost of re-fetching (and harmlessly
re-upserting) one boundary record per run.

## How duplicates are avoided
Every write is `INSERT ... ON DUPLICATE KEY UPDATE` keyed on the provider's `id` (the table's primary
key) — loading is idempotent by construction, so replaying a page is always safe. Within one API
response, occasional repeated rows (the mock server does this deliberately) are deduplicated before the
upsert. Across runs, the data upsert, the reject-quarantine insert, the checkpoint update and the run
counters are all committed in **one MySQL transaction per page**. A kill at any point — mid-page, between
pages, between runs — leaves the table and the checkpoint consistent with each other: replaying never
creates duplicates (`INSERT ... ON DUPLICATE KEY UPDATE`) and never skips rows (the checkpoint only moves
forward once its page is durably committed). This was demonstrated by killing the process with `SIGKILL`
mid-page and rerunning; see `evidence/run_transcript.txt`.

## How failures are handled
- **429 (rate limited):** sleep for the `Retry-After` header value, retry the same request, up to
  6 attempts before the run fails cleanly (checkpoint untouched, safe to retry on the next schedule tick).
- **500 / network errors:** exponential backoff (1s, 2s, 4s, ... capped at 30s), same retry ceiling.
- **Dirty data** (unparseable `amount`, missing `player_id`, bad `updated_at`): the record is quarantined
  into `ingest_rejects` with the reason and the full raw JSON payload, and the run continues — bad
  records are never silently dropped, and are re-examinable/replayable later. The `updated_at`-based
  checkpoint still advances past them, so a permanently-bad record can't wedge the pipeline forever.

## Monitoring
Every run writes one row to `ingest_runs`: pages fetched, rows upserted, rows rejected, 429/500 counts,
start/finish time and final status (`COMPLETED` / `FAILED` / `INTERRUPTED` / stuck `RUNNING`). `checks.sql`
includes the query an on-call alert would run: a run stuck `RUNNING` past one scheduling interval means the
process died without updating its own status (SIGKILL, host crash) — the data is still safe, but ops
should know a scheduled run didn't finish cleanly.

## What I'd change for production
- **Scheduling:** a managed scheduler (Airflow/Cloud Composer/cron + systemd) running this every few
  minutes, with a lock (e.g. `GET_LOCK()` in MySQL or a scheduler-native concurrency guard) so two
  overlapping runs can't both claim the checkpoint at once.
- **Secrets:** `API_KEY` and DB credentials move out of source into a secrets manager / environment
  injected at deploy time, not hardcoded constants as in this exercise.
- **Alerting:** page on `FAILED` runs, on a stale `RUNNING` row, and on a rejects rate above a threshold
  (a sudden spike usually means the provider changed its schema, not that the data is randomly dirty).
- **Scale:** move from `executemany` row-by-row upserts to a staging-table + bulk `MERGE`/`LOAD DATA`
  pattern once volumes go from hundreds to millions of rows per run; partition `transactions` by date if
  history grows large; consider a proper distributed lock and multiple workers pulling disjoint id ranges
  if one API key's rate limit becomes the bottleneck.
- **Cursor robustness:** confirm with the real provider whether the cursor is ever guaranteed on the last
  page (this mock deliberately omits it when `has_more=false`); if guaranteed, prefer resuming from the
  live cursor over `updated_since` to avoid the one-row boundary re-fetch entirely.
