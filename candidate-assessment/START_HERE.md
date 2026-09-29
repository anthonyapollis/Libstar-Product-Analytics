# JSB Data Engineer Practical Assessment: start here

This ZIP holds the complete submission for the three exercises. It contains the write-up, the
working code, the data, the evidence and a portable Power BI project. Every file in it is listed
with its SHA-256 in `MANIFEST.sha256`.

## 1. Read (about 30 minutes)

| Step | Open | What you get |
|---|---|---|
| 1.1 | `JSB_Candidate_Submission.pdf` | The full write-up (29 pages). Page 2 has the contents and pages 4–5 the requirements index, which maps every question in the brief to the section and page that answers it |
| 1.2 | `exercise1-reconciliation/Finance_Summary.pdf` | The one-page Finance Manager summary for Exercise 1 |
| 1.3 | `INDEX.md` | A map from each result to the file that proves it |

Where each exercise is answered in the PDF:

| Exercise | PDF chapter | Pages |
|---|---|---|
| 1. Payment gateway reconciliation | §1.1–1.7 | 6–10 |
| 2. Incremental, restartable API ingestion | §2.1–2.7 | 11–15 |
| 3. Players, wallets, bets and bonuses | §3.1–3.8 | 16–21 |
| Power BI reporting model and report | §4.1–4.4 | 22–26 |
| Databricks version of all three exercises | §5.1–5.2 | 27–28 |
| Appendix A: files and how to reproduce | A | 29 |

## 2. Inspect: the expected results

| Area | Folder | Result you should see | Proof in this ZIP |
|---|---|---|---|
| Exercise 1 | `exercise1-reconciliation/` | 274 of 306 settlements match exactly. 43 exceptions in `exceptions.csv`. The bridge runs from R218,280.00 (internal) to R217,979.97 (gateway) with **R0.00 unexplained** | `summary.md`, `Reconciliation_Workbook.xlsx`, `screenshots/` |
| Exercise 2 | `exercise2-ingestion/` | 1,024 transactions loaded and 1 quarantined. Killed mid-page and restarted with 0 duplicates and 0 missing. 25 new and 40 changed records picked up incrementally. Unit tests 9/9. Postman Runner 17/17, and 1,027 raw records over 6 pages | `evidence/run_transcript.txt`, `evidence/newman_*.txt`, `screenshots/` |
| Exercise 3 | `exercise3-schema-design/` | 24 tables and 39 CHECK constraints. Queries (a)–(d) answered from the seed data. Ledger posting test 17/17 (replay, reversal, concurrency) | `ddl.sql`, `erd.png`, `design_notes.md`, `evidence/` |
| dbt | `dbt_jsb_assessment/` | `dbt build`: 78/78 pass (24 models, 54 tests), and two models load incrementally | `evidence/dbt_build_output.txt`, `evidence/incremental_run.txt` |
| Windows local run | `local_load/` | XAMPP MariaDB 10.4: 43 tables + 11 views = 54 objects, and `dbt test` 54/54 | `evidence/`, `screenshots/` (genuine captures) |
| Databricks | `databricks/` | A serverless job with all 3 notebooks succeeded, and 32/32 checks reproduce the MySQL/dbt results | `evidence/databricks_run.md`, `screenshots/` |
| Power BI | `powerbi/` | Page 1 shows GGR 260.00, Bonus Cost 40.00, NGR 220.00, Liability 10.00 and 18.18% in the campaign table. Page 4 shows 4 ingestion runs | `expected_values.md`, `screenshots/` |

`evidence/README.md` lists every screenshot: what kind it is (a genuine app capture or a rendered
log), when it was taken, what it shows, and its SHA-256. `TABLE_INVENTORY.md` explains every
database object.

## 3. Run it

| What | How | Instructions |
|---|---|---|
| Power BI | Unzip into a **new, empty folder**, open `powerbi/JSB_Assessment.pbip`, then click **Refresh**. The data is embedded, so there is no path or connection to set | `powerbi/PACKAGE_README.md` |
| Local database + dbt (Windows, XAMPP) | Run `local_load\setup_local.bat` | `local_load/README.md` |
| Each exercise on its own (MySQL/MariaDB + Python) | The commands in each exercise's README | `README.md` (Quickstart) |
| Databricks | Import `databricks/notebooks/` and run notebooks 01 → 02 → 03 | `databricks/README.md` |

## 4. Check the ZIP is intact

In the unzipped `JSB_Candidate_Submission` folder, run one of these:
- Linux or macOS: `sha256sum -c MANIFEST.sha256`
- Windows PowerShell:
  `Get-Content MANIFEST.sha256 | % { $h,$f = $_ -split '\s+',2; if ((Get-FileHash -Algorithm SHA256 $f).Hash.ToLower() -eq $h) {"OK    $f"} else {"FAIL  $f"} }`

Every line should say `OK`. The Power BI project also has its own `powerbi/MANIFEST.sha256`.

## 5. Kept in the repository, not in this ZIP

Some documents mention the files below. They were left out on purpose because a reviewer doesn't
need them to read, check or run the work. All of them are on the GitHub branch
`claude/sleepy-hawking-uiq0u9` under `candidate-assessment/`.

| Left out | Why |
|---|---|
| `JSB_Candidate_Submission.docx`, `exercise1-reconciliation/Finance_Summary.docx` | Editable copies of the PDFs above |
| `submission_build/` | The script that generates the PDF |
| `CODEX_REVIEW.md`, `HANDOFF_CODEX.md` | The independent QA log |
| `deliverables/` (including `JSB_PowerBI_v8.zip`) | Separate packages. The same Power BI project is included here, unzipped |
| `evidence/POWERBI_PACKAGE.md`, `evidence/LOCAL_SETUP_PACKAGE.md`, `evidence/powerbi_v7_files.sha256`, `evidence/local_setup_v5_files.sha256` | Provenance of those separate packages |
| `evidence/rejected/` | Captures of an old Power BI copy, kept as a record of why they were rejected |
| `exercise2-ingestion/screenshots/03_…`, `05_…`, `06_…` | Earlier Postman Runner captures, replaced by the clean run in `09_…` and `10_…` |
| `exercise2-ingestion/screenshots/09_postman_runner_all_tests_pass.png`, `10_postman_runner_pagination_complete.png`, `local_load/screenshots/07_windows_xampp_dbt_test_pass.png` | Byte-identical copies of `09_postman_runner_clean_summary.png`, `10_postman_runner_clean_count_1027.png` and `07_windows_xampp_dbt_test.png` |
| `powerbi/data/mart_ngr_by_product_monthly.csv`, `powerbi/data/mart_bonus_cost_pct_of_ngr.csv` | The Power BI model doesn't read them, because it computes both through DAX measures. The same results are in `exercise3-schema-design/evidence/example_queries_output.txt` |
| `local_load/00_drop_other_build_tables.sql` | Withdrawn, and does nothing |
| `.gitignore`, `.gitattributes` | Git settings |
