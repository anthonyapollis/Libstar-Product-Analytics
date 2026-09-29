# Assignment requirements and execution-evidence audit

**Source assessed:** `Candidate_Brief_Practical_Exercises.docx` supplied by the candidate. This is a fact check of the brief, not a replacement for it. “Covered” means there is a deliverable and reproducible evidence in the repository; it does not claim a Windows/XAMPP UI run unless that capture exists.

## Overall result

The implementation covers every stated deliverable and technical requirement. The remaining proof gap is **environment-specific visual evidence**: current files prove container MariaDB/dbt and Databricks runs, while the final submission still needs genuine Windows MySQL/MariaDB, dbt, Power BI, and Databricks job UI screenshots to make that proof easy for a reviewer to inspect.

## Requirement traceability

| Brief requirement | Coverage | Repository evidence | Audit status |
|---|---|---|---|
| Ex1: reconcile both supplied files and identify every difference | Raw tables, matching rules, exceptions, independent cross-check | `exercise1-reconciliation/sql/03_reconciliation.sql`, `exceptions.csv`, `evidence/agreement_by_category.csv` | Covered |
| Ex1: category, classification, cause, impact, next action and owner | Every exception has a row-level explanation and owner; 13 category summary | `exceptions.csv`, `summary.md`, `Finance_Summary.pdf` | Covered |
| Ex1: one-page Finance summary with bridge | Single-page Finance Summary, bridge residual 0.00 | `Finance_Summary.pdf`, `.docx` | Covered |
| Ex1: daily automation and alerts | Daily landing, dbt categorisation, alert tiers and ageing documented | `summary.md`, candidate submission | Covered |
| Ex2: load all then only new/changed API transactions | Idempotent upsert, version guard and incremental dbt fact | `ingest.py`, `verify_against_api.py`, `incremental_run.txt` | Covered |
| Ex2: safe kill/restart, no duplicates/missing rows | Transactional page commit, checkpoint, run lock, restart demo | `demo.py`, `run_transcript.txt`, unit tests | Covered |
| Ex2: cope with API errors/rate limits/unclean data without silent loss | Retry/backoff, quarantine, duplicate payload protection | `ingest.py`, `ingest_rejects`, tests, Newman evidence | Covered |
| Ex2: monitoring, instructions, half-page design note, correctness queries | Run audit tables, README, design note, `checks.sql` | `exercise2-ingestion/` | Covered |
| Ex3: tables, PK/FK/types, constraints and indexes | 24 operational tables, 39 CHECKs, ERD and DDL | `ddl.sql`, `erd.png`, `design_notes.md` | Covered |
| Ex3: correct balance, corrections/reversals, point-in-time proof | Append-only ledger, idempotent/locking procedures, reversal test | `ledger_posting.sql`, `ledger_posting_test.txt` | Covered |
| Ex3: history, privacy, regulator use | SCD2 VIP/tag/status/KYC history; PII split | `SCHEMA_REQUIREMENTS_TRACEABILITY.md`, `design_notes.md` | Covered |
| Ex3: four requested analysis questions and reporting model | Queries (a)–(d), dbt facts/dimensions/marts and Power BI model | `example_queries.sql`, `dbt_jsb_assessment/`, `powerbi/` | Covered |
| General: state tools, assumptions, working files and reproducibility | Tools/assumptions stated; code, SQL, workbook, CSV, ERD, dbt and notebooks included | `README.md`, `INDEX.md`, candidate submission | Covered |

## Execution proof already present

| Environment / tool | Current evidence | Result |
|---|---|---|
| MariaDB 10.11 | `local_load/evidence/object_counts.txt` | 30 base tables, 13 marts, 11 views; 43 tables + 11 views = 54 objects; no table lacks a primary key. |
| dbt | `dbt_jsb_assessment/evidence/dbt_build_output.txt`, `screenshots/01_dbt_build.png` | 24 models, 54 tests, 78/78 pass. |
| Reconciliation SQL | two screenshots and independent category CSV | MySQL logic, pandas check and dbt agree; bridge residual 0.00. |
| API / Postman | Newman transcripts and eight captures | Pagination, retry, rate-limit, new activity, restart and final record count demonstrated. |
| Exercise 3 SQL | query-output and ledger-test evidence | Required queries answered; posting test 17/17. |
| Databricks local | `databricks/evidence/local_test_run.txt`, screenshot | 32/32 checks on Spark 4 + Delta 4. |
| Databricks serverless | `databricks/evidence/databricks_run.md` | One job, three tasks SUCCESS; 32/32 checks. |

## Evidence still required for a submission-quality proof pack

These must be genuine captures from the stated application, with no fabricated or recreated terminal image.

1. **Windows MySQL/MariaDB:** MySQL Workbench or phpMyAdmin showing the four JSB schemas and the final 6 / 24 / 13 / 11 object distribution; a query-result capture of the 54-object total and “no tables without a primary key”.
2. **dbt on the same local server:** terminal capture of `dbt debug` success and `dbt build --full-refresh` ending `PASS=78, ERROR=0`, with the target/adapter/version visible.
3. **MySQL/MariaDB exercise results:** result-grid capture of the reconciliation summary (274 exact matches and R0.00 bridge) and Exercise 3 query output/ledger test.
4. **Postman:** retain the existing Postman/Newman captures and add one final Collection Runner summary that shows all selected requests and zero unexpected assertion failures, if the one-shot pagination request remains part of the collection.
5. **Power BI Desktop:** one full capture of each of the four report pages after refresh, plus Model view. Use `powerbi/expected_values.md` as the visible-value checklist.
6. **Databricks serverless:** job-run page showing the parent job SUCCESS and each ex1/ex2/ex3 task SUCCESS; retain the current local-test screenshot as supporting evidence.
7. **Evidence index:** add each capture with timestamp, environment, command/action, expected outcome, observed outcome, and SHA-256. Link it from the submission and `INDEX.md`.

## Acceptance standard

The project may be described as fully evidenced only once the repository contains the genuine screenshots above, a manifest linking each image to its run output, and the submission PDF states where that evidence lives. Until then, the code and text are comprehensive, but the Windows/UI portion is reproducible rather than independently visualised.