# Exercise 2: incremental, restartable API ingestion

Loads the mock provider's transactions into MySQL/MariaDB. The first run loads everything; later
runs load only new and changed records. It is safe to kill at any moment, never creates
duplicates, and quarantines bad records rather than dropping them. The design is in
`design_note.md` (half a page).

## Deliverables
| Brief asks for | File |
|---|---|
| Code | `ingest.py` (the loader), `schema.sql` (its 4 tables) |
| Instructions to run it | this file |
| Half-page design note | `design_note.md` |
| Queries used to check correctness | `checks.sql` (SQL) and `verify_against_api.py` (every id against the API) |
| Evidence: run, interrupt, rerun, new activity | `demo.py` → `evidence/run_transcript.txt` |
| Tests | `tests/`: exit codes, lock, validation, new/changed classification (no network or DB needed) |

## Requirements
- Python 3.9+ with `pip install pymysql`. The mock API itself needs only the standard library.
- MySQL 8 or MariaDB 10.4+.

Connection settings are read from the environment. The defaults are the mock API and the build
container:

| Variable | Default | XAMPP example |
|---|---|---|
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | same |
| `DB_USER` / `DB_PASSWORD` | `assess` / `AssessPass123!` | `root` / *(empty)* |
| `DB_NAME` | `jsb_assessment` | same |
| `INGEST_API_BASE` / `INGEST_API_KEY` | `http://127.0.0.1:8000` / `test-key` (from the API doc) | same |

On Windows (Command Prompt), set them like this:
```bat
set DB_USER=root
set DB_PASSWORD=
```

## Run it
```bash
mysql -u root jsb_assessment < schema.sql   # once: creates the 4 tables (drops them if present)
python mock_api.py                          # terminal 1: the provider on port 8000
python ingest.py                            # terminal 2: run it every few minutes (cron / Task Scheduler)
python verify_against_api.py                # every id in the table vs the API: missing / stale / duplicates
mysql -u root jsb_assessment < checks.sql   # correctness and monitoring queries
```

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | Completed, or skipped because another run holds the lock |
| 1 | Failed: retries exhausted or an API error |
| 130 | Interrupted with Ctrl+C |

## Reproduce the evidence in one command
```bash
python demo.py                     # uses its own database, jsb_ingest_demo
python -m unittest discover -s tests
```

`demo.py` does the following, and writes everything it prints to `evidence/run_transcript.txt`:
1. Starts the mock API with faults on (429s, 500s and repeated rows).
2. Hard-kills a run mid-page, then shows that only the committed page is in the table.
3. Restarts the run. It marks the killed run ABANDONED and resumes from the checkpoint.
4. Checks every id against the API.
5. Reruns with no provider changes: 0 new, 0 changed.
6. Calls `POST /admin/advance`, the interviewer's step.
7. Reruns: 25 new, 40 changed.
8. Checks against the API again: 1,025 ids = 1,024 loaded + 1 quarantined, with 0 missing, 0 stale
   and 0 duplicates.

## Postman
The collection in `postman/` exercises the API contract: the auth header, paging, 429/500 handling
and a full record count.

**Count every record:**
1. Import the collection and the environment.
2. Run the collection with the **Collection Runner**. In the app, **Send** on a single request
   doesn't follow `setNextRequest`, so it won't page through.
3. The last test name shows the total number of rows returned. That total includes the mock's
   deliberately repeated rows, so it's a little higher than the number of unique ids.

**From the command line:**
```bash
newman run postman/JSB_Assessment_Exercise2.postman_collection.json -e postman/JSB_Assessment.postman_environment.json
```

## Files
| File | What it is |
|---|---|
| `schema.sql` | `transactions` (primary key `id`), `ingest_checkpoint`, `ingest_runs`, `ingest_rejects` (unique per bad payload) |
| `ingest.py` | The loader |
| `verify_against_api.py` | Checks the table against the API |
| `demo.py` | The end-to-end evidence run |
| `checks.sql` | SQL checks: duplicates, reject accounting, run history, stale runs, checkpoint |
| `design_note.md` | Design, and what would change in production |
| `tests/` | Unit tests |
| `postman/`, `evidence/`, `screenshots/` | Postman collection, transcripts, screenshots |
