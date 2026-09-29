# Final submission ZIP: provenance

| Item | Value |
|---|---|
| File | `deliverables/JSB_Candidate_Submission_Final.zip` (committed on branch `claude/sleepy-hawking-uiq0u9`) |
| SHA-256 | `244aebe76e4016582879f032a9ac36d02d532803afd3756d13c23efab7f73d71` |
| Size | 4,585,124 bytes |
| Files | 168: 167 content files + `MANIFEST.sha256` (all under `JSB_Candidate_Submission/`) |
| Source commit | `5512d6f363ac10aee629a9b1a802c1272edd05f6` |
| Built by | `python submission_build/build_final_zip.py 5512d6f` (`git archive` of `candidate-assessment/`, repository-only files removed, fixed timestamps) |
| File list | [`final_submission_manifest.sha256`](final_submission_manifest.sha256), a copy of the ZIP's own `MANIFEST.sha256` |
| eBook inside | `JSB_Candidate_Submission.pdf`: 29 pages, SHA-256 `f37ab5ac42c3da2efec8bfea6df87fd7732661106e3624841673d0857b8e12a6`, byte-identical to the committed PDF |

## Files per folder
| Folder | Files |
|---|---:|
| Root: PDF, `START_HERE.md`, `INDEX.md`, `README.md`, `TABLE_INVENTORY.md`, `ASSIGNMENT_REQUIREMENTS_EVIDENCE.md`, `SCHEMA_REQUIREMENTS_TRACEABILITY.md` | 7 |
| `exercise1-reconciliation/` | 18 |
| `exercise2-ingestion/` | 22 |
| `exercise3-schema-design/` | 13 |
| `dbt_jsb_assessment/` | 37 |
| `local_load/` | 17 |
| `databricks/` | 15 |
| `powerbi/` (the v8 project once, unzipped, with its 11 data CSVs) | 34 |
| `evidence/` (includes `screenshot_crops.md`) | 4 |
| **Total (plus `MANIFEST.sha256`)** | **167 + 1** |

## Checks run on a clean extraction (2026-09-29)
| Check | Result |
|---|---|
| Rebuilding from the same commit gives the same bytes | `cmp` identical |
| `sha256sum -c MANIFEST.sha256` | 167/167 OK |
| `powerbi/`: `sha256sum -c MANIFEST.sha256` | 21/21 OK |
| No `.zip`, `.docx`, `__pycache__`, `.git*`, database files or virtual environments | none found |
| `local_load/setup_local.bat` line endings | CRLF (`.gitattributes` applied by `git archive`) |
| Every path named in `START_HERE.md` §1–4 exists at that path | all present |
| No uncropped full-screen (1366×768) capture in any `screenshots/` folder | none |
| Bronze/Silver/Gold callout in the PDF | §3.8, page 20, the three requested lines only |

What was left out, and why, is in `START_HERE.md` §5.

## Rebuild history
| Build | SHA-256 | Change |
|---|---|---|
| 1 (commit `a654356`) | `6c5ecc40…0724614d8d2` | First build. Codex approved it in 179fcf7 |
| 2 (commit `56aebb1`) | `5db73215…d574031968` | `START_HERE.md` only: `exceptions.csv` has 49 rows (43 is the Power BI count, which treats the 6 reference-formatting variants as matched), and a line on why this record is kept outside the ZIP. The other 165 files are byte-identical to build 1 |
| 3 (commit `5512d6f`, current) | `244aebe7…ab7f73d71` | QA-19. 16 captures in the ZIP were pixel-cropped to the producing application; three more cropped duplicates stay in the repository only. The evidence hashes and the eBook were updated, and `evidence/screenshot_crops.md` was added. No data, model or result changed |
