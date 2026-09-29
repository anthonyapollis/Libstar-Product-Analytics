# Assessment index

This page is the reviewer’s map to the submission. Start with the consolidated write-up, then use the evidence links below to trace every result to its reproducible source.

## Submission and quick review

| Need | Start here | Evidence / result |
|---|---|---|
| Candidate submission | `JSB_Candidate_Submission.pdf` or `.docx` | 22-page consolidated write-up (Exercises 1–3, Power BI, Databricks) |
| Object inventory and duplication rationale | `TABLE_INVENTORY.md` | 30 base tables + 13 dbt marts + 11 staging views = 54 objects (fresh count: `local_load/evidence/object_counts.txt`) |
| Build/run instructions | `local_load/README.md` | `setup_local.bat` for local XAMPP MariaDB + dbt |
| Claude/Codex delivery status | `HANDOFF_CODEX.md` and `CODEX_REVIEW.md` | Build notes and independent QA record |

## Exercise evidence

| Exercise | Deliverables | Verified result |
|---|---|---|
| 1 — reconciliation | `exercise1-reconciliation/summary.md`, `Finance_Summary.pdf`, `exceptions.csv`, `Reconciliation_Workbook.xlsx` | 274 of 306 settlements match exactly; the R218,280.00 → R217,979.97 bridge has R0.00 unexplained. |
| 2 — API ingestion | `exercise2-ingestion/README.md`, `design_note.md`, `postman/`, `evidence/run_transcript.txt` | 1,024 loaded + 1 quarantined; no missing, stale or duplicate provider records. |
| 3 — operational schema | `exercise3-schema-design/design_notes.md`, `ddl.sql`, `erd.png`, `evidence/ledger_posting_test.txt` | 24 operational tables; 39 CHECK constraints; ledger posting test 17/17. |
| dbt reporting | `dbt_jsb_assessment/README.md`, `evidence/dbt_build_output.txt`, `evidence/incremental_run.txt` | 24 models and 54 tests; `dbt build` 78/78 pass. |
| Power BI | `powerbi/README.md`, `expected_values.md`, `model.png` | 4 pages, 11 tables, 7 relationships, 28 measures. |
| Databricks | `databricks/README.md`, `evidence/databricks_run.md`, `evidence/local_test_run.txt` | Serverless job SUCCESS across all three notebooks; 32/32 checks. |

## Canonical object totals

| Layer | Physical tables | Views | Total objects |
|---|---:|---:|---:|
| Exercise 1 and 2 source | 6 | 0 | 6 |
| Exercise 3 operational | 24 | 0 | 24 |
| dbt marts | 13 | 0 | 13 |
| dbt staging | 0 | 11 | 11 |
| **Fresh local load + dbt build** | **43** | **11** | **54** |

`player_status_history` is a required operational history layer for account status/KYC at the time of a bet. It is deliberate, not a duplicate. Raw reconciliation duplicates and ingestion audit/reject records are deliberately retained because they are evidence of source quality and restartability.

## Reviewer sequence

1. Read `JSB_Candidate_Submission.pdf` and `Finance_Summary.pdf`.
2. Confirm the figures against the linked evidence above.
3. Use `TABLE_INVENTORY.md` to trace each database object and confirm it has a purpose.
4. Run the local build only in the clean target schemas, then run `dbt build`.
5. Open the Power BI project and compare each visual to `powerbi/expected_values.md`.