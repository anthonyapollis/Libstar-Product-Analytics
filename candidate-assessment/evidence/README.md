# Evidence manifest (QA-10)

Every image in the submission, what produced it, and its SHA-256, so a reviewer can tie each picture to
a run and a commit. The three kinds are kept apart on purpose:

| Kind | Meaning |
|---|---|
| **App capture** | A real screenshot of the named application, taken on the user's Windows PC (Postman, PyCharm, MySQL Workbench, cmd.exe). |
| **Rendered log** | Real command output from a run in the build container, captured to the text file named. `submission_build/make_screenshot.py` then drew it as a terminal-style image. **The log file is the primary evidence**; the image is a readable copy of it, not a screen capture. |
| **Generated diagram** | Drawn from source (Mermaid) by the build, not a run result. |

Times are UTC. "Commit" is the commit that added the current version of the file. Check any file with
`sha256sum <path>` (Windows: `certutil -hashfile <path> SHA256`).

## Windows / XAMPP (user's PC, MariaDB 10.4.24, dbt 1.7.20 + mariadb 1.7.0)

| File | Kind | Time | Action | Expected | Observed | Commit | SHA-256 |
|---|---|---|---|---|---|---|---|
| `local_load/screenshots/00_windows_xampp_step1_load.png` | App capture (cmd.exe) | 2026-09-29 05:17 | `setup_local.bat` step 1 | 326 / 306 / 1,024 / 4 / 1 rows; 24 `jsb_platform` tables | as expected | `59b1079` | `8077b176b909202c07813d35a2d86323675c9e00266ed6255aab3415683de935` |
| `local_load/screenshots/01_windows_xampp_dbt_debug.png` | App capture (cmd.exe) | 2026-09-29 05:21 | `dbt debug --target xampp` | connection OK, "All checks passed!" | as expected | `7a3e803` | `54c5b1607b3a2a583af34e0ffd7968b0327e7ddede344e30df94d74529aea626` |
| `local_load/screenshots/02_windows_xampp_dbt_staging.png` | App capture (cmd.exe) | 2026-09-29 05:58 | `dbt run --select staging` | 11 views | `PASS=11 ERROR=0` | `59b1079` | `eae3036924a31e0e760175d1b0ba154cf5070eb2dc8e1ec2d73e5120795c7c19` |
| `local_load/screenshots/03_windows_xampp_dbt_marts.png` | App capture (cmd.exe) | 2026-09-29 05:59 | `dbt run --select marts --full-refresh` | 13 tables (2 incremental) | `PASS=13 ERROR=0`; `fact_wallet_transaction` 18, `fact_bet` 6, `fct_recon_exceptions` 317 rows | `59b1079` | `5b97194c17ed7835cb09bf3ddb3195635798d193f5fef327b42c4257dfbbb64c` |
| `local_load/screenshots/06_windows_xampp_proof_queries.png` | App capture (cmd.exe, mysql.exe -t) | 2026-09-29 07:06 | `mysql.exe -u root -t < proof_queries.sql` | 6 / 24 / 13 / 11 = 43 tables + 11 views = 54; no table without a PK; 274 OK of 317; bridge residual 0.00 | as expected (the PK query returned no rows, so no grid is printed for it) | `cc822ec` | `4e22bceaff0ba155a358f5f2e334d60cfbbf2bc14fdc244cadbc0f152a7dc7bc` |
| `local_load/screenshots/07_windows_xampp_dbt_test.png` | App capture (cmd.exe) | 2026-09-29 07:11 | `dbt.exe test --target xampp` (setup step 6) | 54 tests pass | `PASS=54 WARN=0 ERROR=0 SKIP=0 TOTAL=54` in 5.82 s | `5ed6ca1` | `27c83a9a4d9d15f01f468d866f4180a81c0a8c8976cb1cbc8a567b79186e01a4` |
| `local_load/screenshots/04_windows_workbench_jsb_assessment.png` | App capture (MySQL Workbench) | 2026-09-29 05:15 | Navigator after step 1 | `jsb_assessment`: 6 tables | 6 tables | `59b1079` | `5f6af4fb502f323599909bfbab2e024f4a59d99bda587cf36af80e16a6e688ae` |
| `local_load/screenshots/05_windows_workbench_jsb_platform.png` | App capture (MySQL Workbench) | 2026-09-29 05:16 | Navigator after step 1 | `jsb_platform` tables | table list visible | `59b1079` | `be413140c499127a79c8f69a2c8e012c5c98e89978ceddbe9936003fd88d4420` |

The full Windows run, including step 6 (`dbt test`, `PASS=54`), the 43 + 11 = 54 object count and the
zero-missing-primary-key check, is recorded in `local_load/evidence/windows_xampp_run_20260929.md`.

## Power BI Desktop (user's PC, fresh unzip of `JSB_PowerBI_v7.zip`, refreshed)

| File | Kind | Time | Action | Expected | Observed | SHA-256 |
|---|---|---|---|---|---|---|
| `powerbi/screenshots/01_page1_ngr_overview.png` | App capture (Power BI Desktop) | 2026-09-29 06:52 | open v7, Refresh, Page 1 | 260 / 40 / 220 / 10; 18.18% | as expected | `af4916d8cb71a702497a73fdd47a4e193a14323ae8d4af37a84bbf2863d797e4` |
| `powerbi/screenshots/02_page2_player_balances.png` | App capture (Power BI Desktop) | 2026-09-29 06:53 | Page 2, full date range | 890 / 415 + 0 / 90 + 10; deposits 1,600 | as expected | `9bb99667b6a6ac3329b6c5f90eb9f3ac79756e66c289ad6c8d96e98468f55907` |
| `powerbi/screenshots/03_page3_reconciliation.png` | App capture (Power BI Desktop) | 2026-09-29 06:53 | Page 3 | 274 / 43 / 3,150.00 / 0.00 | as expected | `e52d1b70eaaab42710459e0d75f8700dbd5c67f01fd1741856f6cfa0d121a096` |
| `powerbi/screenshots/04_page4_ingestion_monitoring.png` | App capture (Power BI Desktop) | 2026-09-29 06:53 | Page 4 | 1,024 / 4 / 1 / 1; 587 / 214 / 207 / 16 | as expected | `de5957e01ee0f4464a6d7f7db89746a27e9698d4f25072cf09cd37e63f66f624` |

## Postman / PyCharm (user's PC)

| File | Kind | Time | Action | Expected | Observed | Commit | SHA-256 |
|---|---|---|---|---|---|---|---|
| `exercise2-ingestion/screenshots/03_postman_runner_config.png` | App capture (Postman) | 2026-09-28 | Collection Runner set-up | all 7 requests, 1 iteration | as expected | `df739f9` | `3a6784aa09c9a865fdb8db7540722529889e1e83af54b7322c73d527d3814a68` |
| `exercise2-ingestion/screenshots/04_postman_request0_200ok.png` | App capture (Postman) | 2026-09-28 | first page request | 200 OK | 200 OK | `df739f9` | `b673dd59c8d2642169a06147a31958d4d8c1dbef74ef6e6749ff7e6c76f0fe6f` |
| `exercise2-ingestion/screenshots/05_postman_runner_pages_1_to_4.png` | App capture (Postman) | 2026-09-28 | Runner, pages 1–4 | paginated 200s | as expected | `df739f9` | `5db67f147b43beb1c7971b11d1f851db42de35e8b1485122c524b65ecb9139fc` |
| `exercise2-ingestion/screenshots/06_postman_runner_total_1027.png` | App capture (Postman) | 2026-09-28 | Runner, pages 4–6 | "DONE", all rows returned | 1,027 rows over 6 pages; two assertions failed on request 2 (see note) | `df739f9` | `030dece9202a7c36b79042627f9ebed18cd07894cda4665fc5ce7ec61152d8c6` |
| `exercise2-ingestion/screenshots/09_postman_runner_clean_summary.png` | App capture (Postman) | 2026-09-29 07:14 | Collection Runner, all 7 requests; mock API started with `--no-faults` | no unexpected failures | **17 tests: 17 passed, 0 failed, 0 errors**; every request 200 | @@C@@ | `d56ef54c34774c94121bbf2fe9e73d35d03ea822f267e980370d93568013f9b7` |
| `exercise2-ingestion/screenshots/10_postman_runner_clean_count_1027.png` | App capture (Postman) | 2026-09-29 07:14 | same run, end of request 6 (auto-paginating count) | all pages read to the end | 6 pages, "DONE -- TOTAL RECORDS RETURNED BY API: 1027" | @@C@@ | `def3a1c6fe148047b0f9aab8983e48359286ebe5849afe6180e5c975b93d48c9` |
| `exercise2-ingestion/screenshots/07_pycharm_mock_api_running.png` | App capture (PyCharm) | 2026-09-28 | mock API running | server up | as expected | `df739f9` | `de49fc2480f5e84fd4c27159af54d1da442d18b94b8ee1329685cd595868adf9` |

## Databricks (user's workspace, Jobs UI)

| File | Kind | Time | Action | Expected | Observed | SHA-256 |
|---|---|---|---|---|---|---|
| `databricks/screenshots/02_serverless_job_success.png` | App capture (Databricks Jobs UI, Edge) | 2026-09-29 07:02 | open job run 460654207301296 ("JSB assessment - all exercises run"), Graph view | ex1 → ex2 → ex3 all Succeeded on serverless | ex1 Succeeded 53s, ex2 Succeeded 2m 50s, ex3 Succeeded 4m 54s; all Serverless | `843958550f3e935a3625f080eb9ba223198ede95dacaf0233791c1367a85be08` |

## Rendered logs (build container, MariaDB 10.11)

| File | Source log | Time | Result | Commit | SHA-256 |
|---|---|---|---|---|---|
| `exercise1-reconciliation/screenshots/01_reconciliation_categories_and_bridge.png` | output of `sql/03_reconciliation.sql` (reproduced by `sql/04_independent_check.py`) | 2026-09-28 | 274 matched; bridge residual 0.00 | `87f812c` | `9298f7b2468b6a9f9fba22c9ed3e95a1e150be9be92a3080c4ccd009345d1c6c` |
| `exercise1-reconciliation/screenshots/02_three_way_agreement.png` | `exercise1-reconciliation/evidence/agreement_by_category.csv` | 2026-09-28 | SQL = dbt = pandas on all 317 rows | `87f812c` | `21e0019a61360306ed771556f1af1bed4a74a8f5675f1581f0a568a7e12098da` |
| `exercise2-ingestion/screenshots/01_kill_restart_new_activity.png` | `exercise2-ingestion/evidence/run_transcript.txt` | 2026-09-28 | kill, restart, rerun, new activity: PASS | `cef2944` | `befa931f220ce6269bc3d9289476d0a857ed7dbf18ebd8b09a6fa2874eefd184` |
| `exercise2-ingestion/screenshots/02_postman_newman_run.png` | `exercise2-ingestion/evidence/newman_run_clean.txt` | 2026-09-28 | 5 requests, 0 failed | `c9b58ba` | `baa5214b02f5b65e195fa5f1d888cc48952c09c747ec76639a5fb76656c86216` |
| `exercise2-ingestion/screenshots/08_new_activity_final_state.png` | `exercise2-ingestion/evidence/run_transcript.txt` | 2026-09-28 | 25 new + 40 changed; table = API | `cef2944` | `a5e7c1a08f2609d68080cee8d960b87c5553553f93a51b8701dbf47e1b669fc5` |
| `exercise3-schema-design/screenshots/01_example_queries_output.png` | `exercise3-schema-design/evidence/example_queries_output.txt` | 2026-09-28 | NGR 220.00; 18.18%; 1,160.00; 450 → 415; 4 min | `5574303` | `1e8140ffc3fa1a35781dec52c335296023ebc268f3fa7b1ed48238755434c3c3` |
| `exercise3-schema-design/screenshots/02_ledger_posting_test.png` | `exercise3-schema-design/evidence/ledger_posting_test.txt` | 2026-09-28 | 17/17 PASS | `5574303` | `209da1266ecfdcff12876409fba9fd844c7335e3780304b43d90ee182a94c00f` |
| `dbt_jsb_assessment/screenshots/01_dbt_build.png` | `dbt_jsb_assessment/evidence/dbt_build_output.txt` | 2026-09-28 | 78/78 PASS | `5574303` | `070215d94a2f762030d8c979e9eaa41a1f3531e76d4099f84e88f06390845e5e` |
| `databricks/screenshots/01_local_test_run.png` | `databricks/evidence/local_test_run.txt` | 2026-09-29 | 32/32 PASS (Spark 4 + Delta 4) | `76a61dd` | `3c4f8b3fe0b7ec207bd5c4f1d0195dc0c068157388d56e3a8502e09ef062d5a6` |

The Databricks serverless run itself is recorded in `databricks/evidence/databricks_run.md`: job and
task run URLs, all SUCCESS, from the Jobs API.

## Generated diagrams

| File | Source | Commit | SHA-256 |
|---|---|---|---|
| `exercise3-schema-design/erd.png` | `exercise3-schema-design/erd.mmd` | `5574303` | `91249e1e32fd922be1f9aecea1e3cdf38f163bca63dd6d74dd3dbdbba1db7873` |
| `powerbi/model.png` | `powerbi/model.mmd` | `5574303` | `dfa12022d2218a3e5c4175d38ad5edd932cf8b8457bd915261936db232b1b007` |

## Still to capture (needs the user's screen)
These can't be produced from the build container. They will be added here, with hashes, when the user
sends them:

| # | Capture | Shows |
|---|---|---|
| ~~P1~~ | **Done**: `local_load/screenshots/07_windows_xampp_dbt_test.png` | |
| ~~P2~~ | **Done**: `local_load/screenshots/06_windows_xampp_proof_queries.png` (cmd.exe; Workbench crashes on MariaDB 10.4) | |
| ~~P3~~ | **Done**: `local_load/screenshots/06_windows_xampp_proof_queries.png` (cmd.exe; Workbench crashes on MariaDB 10.4) | |
| ~~P4~~ | **Done**: see the Power BI section above. The earlier captures of an old copy are kept in `rejected/` only | |
| P5 | Power BI Desktop, Model view | 11 tables, 7 relationships |
| ~~P6~~ | **Done**: `databricks/screenshots/02_serverless_job_success.png` (see the Databricks section above) | |
| ~~P7~~ | **Done**: `exercise2-ingestion/screenshots/09_…` and `10_…` (clean Runner, faults off) | |

**P7 was captured with the mock API's random faults switched off (`--no-faults`)**, so it shows the collection itself passing cleanly. Fault handling is proven separately: `newman_run_with_injected_500.txt` shows the retry path, `run_transcript.txt` shows `ingest.py` riding through 429s, 500s and repeated rows, and capture 06 shows a faults-on Runner.

**Note on P7 and `06_postman_runner_total_1027.png`:** the two failed assertions in that capture are on
request 2 ("Next page"). That is a one-shot documentation request with no retry logic, and it happened
to land on one of the mock API's injected 429 (rate-limit) responses; only the counting request
retries. It is not an API or ingestion failure: the same collection under Newman passes 5/5
(`02_postman_newman_run.png`), and `ingest.py` retries every 429. 1,027 rather than 1,025 is the raw
count including the API's in-page repeated rows, which `ingest.py` collapses. A clean Runner capture
(P7) will replace it.

The SQL for P2 and P3 is in `evidence/proof_queries.sql`, ready to paste into Workbench.
| `local_load/screenshots/07_windows_xampp_dbt_test_pass.png` | App capture (Windows cmd.exe + XAMPP MariaDB) | 2026-09-29 09:11 SAST | `dbt test --target xampp` | All 54 dbt tests pass | `PASS=54 WARN=0 ERROR=0 SKIP=0 TOTAL=54` | `b85ddf4` | `27c83a9a4d9d15f01f468d866f4180a81c0a8c8976cb1cbc8a567b79186e01a4` |