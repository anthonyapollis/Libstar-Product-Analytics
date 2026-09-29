# Handoff: Claude → Codex

Branch: `claude/sleepy-hawking-uiq0u9` · folder: `candidate-assessment/`

**Roles:** Claude builds; Codex verifies.

**How we talk:** Codex writes its findings to `candidate-assessment/CODEX_REVIEW.md` on this branch and pushes. Claude pulls it, fixes each item or answers why not, and replies under each finding in the same file. Codex re-checks and marks each item `VERIFIED` or `STILL FAILING`. Keep each finding to one issue with the exact command or visual and the expected vs actual value.

## What is done

| Area | State | Evidence |
|---|---|---|
| Ex 1 reconciliation | 274 of 306 settlements match exactly. 12 exception types. The bridge R218,280.00 → R217,979.97 leaves R0.00 unexplained. The MySQL script, the dbt model and an independent pandas version agree on all 317 rows and every category. | `exercise1-reconciliation/summary.md`, `sql/04_independent_check.py`, `screenshots/02_three_way_agreement.png` |
| Ex 2 ingestion | Audited against the brief. Adds a run lock, ABANDONED marking, new/changed/unchanged counts, no-regression upserts, a forward-only checkpoint and de-duplicated rejects. `demo.py` reproduces a hard kill, restart, rerun, `/admin/advance` and rerun; `verify_against_api.py` checks every id against the API: 1,025 = 1,024 loaded + 1 quarantined, 0 missing/stale/duplicates. 9 unit tests. | `exercise2-ingestion/evidence/run_transcript.txt` |
| Ex 3 schema | Audited against the brief (tasks 12–18). 24 tables, 39 CHECK constraints, posting procedures (idempotent, locked, cache in the same transaction), one bonus-cost definition everywhere, no ledger status column (reversals can't be double-counted). Queries (a)–(d) answered; `test_ledger_posting.py` 17/17. Details in `CODEX_REVIEW.md`, last section. | `exercise3-schema-design/`, `evidence/` |
| Databricks | 4 notebooks built from the project's own files; 32/32 checks pass locally on Spark 4 + Delta 4. Ran on the user's workspace (serverless) 2026-09-28: one job, all 3 tasks SUCCESS, 32/32 checks; two serverless-only fixes (mock API host/port, generated-column CAST). | `databricks/evidence/databricks_run.md`, `local_test_run.txt` |
| dbt | `dbt build`: 78/78 pass (24 models, 54 tests) on MariaDB 10.11. Every mart has a primary key (`table_keys` post-hook) and a uniqueness test; 2 incremental models | `dbt_jsb_assessment/evidence/dbt_build_output.txt` |
| Power BI | 11 tables, 7 relationships, 28 measures (22 calculations + 6 tile-colour rules), 4 pages, data embedded. The user opened v3 in Desktop and it rendered as designed (banners, coloured tiles, waterfall, category and status colours). v4 makes status tiles follow their value (green / amber / red) via colour measures; expected colours are in `expected_values.md`. | `powerbi/`, `powerbi/expected_values.md` |
| Local database | Old builds removed by Codex, with a backup. `local_load/setup_local.bat` loads the 30 base tables (6 source + 24 Exercise 3), then runs dbt step by step (11 staging views, 13 mart tables, 54 tests): 43 physical tables + 11 views = 54 objects in total, each explained in `TABLE_INVENTORY.md`. | `local_load/README.md`, `TABLE_INVENTORY.md` |
| Write-up | `JSB_Candidate_Submission.docx` / `.pdf`, 23 pages (Exercises 1–3, Power BI, Databricks, with the genuine Windows, Power BI Desktop and Databricks captures) | top-level folder |

## What the user still needs to do
1. **Clean up and load the local database.** Run `local_load/00_drop_other_build_tables.sql`, then `01_load_submission_tables.sql`, in XAMPP MariaDB.
2. **Check Power BI.** Open the latest Power BI zip in a new folder, click Refresh, and check each page against `powerbi/expected_values.md`.
3. **Send screenshots.** Send screenshots of the 4 Power BI pages. Claude will crop them into the submission document, which currently shows only the model diagram for Power BI.
4. **Submit** the docx or pdf.

## Codex: please verify
1. **Power BI Desktop** (Windows): open `powerbi/JSB_Assessment.pbip` and click Refresh. For every row of `expected_values.md`, confirm the visual shows that value. Confirm the styling renders:
   - KPI tiles are coloured, with white values.
   - Act Now shows `3,150.00`, not `3.15K`.
   - The waterfall steps are visible, with green/red/navy bars.
   - The exception bars are coloured by type, with readable labels.
   - The status columns are coloured.

   Report any property Desktop ignored or rejected.
2. **Local database:** run both `local_load` scripts on XAMPP. Confirm the row counts printed at the end, then run `exercise1-reconciliation/sql/03_reconciliation.sql` and confirm 274 matched and the bridge figures in `summary.md`.
3. **Figures consistency:** every number in `JSB_Candidate_Submission.pdf` must match `summary.md`, `expected_values.md` and `dbt_build_output.txt`. List any mismatch with its page number.
4. **dbt (optional):** with the database loaded, `cd dbt_jsb_assessment && dbt build` → 78/78.

Please don't restructure or rename things. Report findings; small, obviously correct fixes may be committed, with a line in `CODEX_REVIEW.md` saying what changed.
