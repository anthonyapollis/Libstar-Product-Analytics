# Exercise 2 — Incremental, restartable API ingestion

**Tools:** Python 3 (stdlib only), MySQL 8.0, Postman/Newman.

## Run it
```bash
# 1. schema (once)
mysql -u assess -p jsb_assessment < schema.sql

# 2. start the mock provider
python mock_api.py

# 3. run the ingestion (repeat every few minutes on a schedule)
python ingest.py

# 4. verify
mysql -u assess -p jsb_assessment < checks.sql

# 5. exercise the API contract directly
newman run postman/JSB_Assessment_Exercise2.postman_collection.json \
  -e postman/JSB_Assessment.postman_environment.json
```

## Files
| File | What it is |
|---|---|
| `schema.sql` | `transactions`, `ingest_checkpoint`, `ingest_runs`, `ingest_rejects` |
| `ingest.py` | The ingestion program |
| `checks.sql` | Correctness + monitoring queries |
| `design_note.md` | How it tracks progress, avoids duplicates, handles failures; production changes |
| `postman/` | API-contract collection + environment, run with Newman |
| `evidence/` | Transcript of the kill/restart/new-activity demonstration, Newman run output |

See `evidence/run_transcript.txt` for the full kill → restart → `/admin/advance` → rerun demonstration
(0 duplicates, 0 missing rows, 1 bad record quarantined not lost, 1 live 429 retried automatically).
