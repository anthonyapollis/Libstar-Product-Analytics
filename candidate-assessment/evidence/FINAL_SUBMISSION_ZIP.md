# Final submission ZIP: provenance

| Item | Value |
|---|---|
| File | `deliverables/JSB_Candidate_Submission_Final.zip` (committed on branch `claude/sleepy-hawking-uiq0u9`) |
| SHA-256 | `5db7321515fd4300a389571b84687a0d80de2260821e29848bbf55d574031968` |
| Size | 6,185,751 bytes |
| Files | 167: 166 content files + `MANIFEST.sha256` (all under `JSB_Candidate_Submission/`) |
| Source commit | `56aebb19f3fe75308d8a353f14a4b1f8d28a4f9e` |
| Built by | `python submission_build/build_final_zip.py 56aebb1` (`git archive` of `candidate-assessment/`, repository-only files removed, fixed timestamps) |
| File list | [`final_submission_manifest.sha256`](final_submission_manifest.sha256), a copy of the ZIP's own `MANIFEST.sha256` |
| eBook inside | `JSB_Candidate_Submission.pdf`: 29 pages, SHA-256 `1a9ec59a225b5f579a0865940a37a5f8e0689c20affbba6128f5a44cc62e4778`, byte-identical to the committed PDF |

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
| `evidence/` | 3 |
| **Total (plus `MANIFEST.sha256`)** | **166 + 1** |

## Checks run on a clean extraction (2026-09-29)
| Check | Result |
|---|---|
| Rebuilding from the same commit gives the same bytes | `cmp` identical |
| `sha256sum -c MANIFEST.sha256` | 166/166 OK |
| `powerbi/`: `sha256sum -c MANIFEST.sha256` | 21/21 OK |
| No `.zip`, `.docx`, `__pycache__`, `.git*`, database files or virtual environments | none found |
| `local_load/setup_local.bat` line endings | CRLF (`.gitattributes` applied by `git archive`) |
| Every path named in `START_HERE.md` §1–4 exists at that path | all present |
| Bronze/Silver/Gold callout in the PDF | §3.8, page 20, the three requested lines only |

What was left out, and why, is in `START_HERE.md` §5.

## Rebuild history
| Build | SHA-256 | Change |
|---|---|---|
| 1 (commit `a654356`) | `6c5ecc40…0724614d8d2` | First build. Codex approved it in 179fcf7 |
| 2 (commit `56aebb1`, current) | `5db73215…d574031968` | `START_HERE.md` only: `exceptions.csv` has 49 rows (43 is the Power BI count, which treats the 6 reference-formatting variants as matched), and a line on why this record is kept outside the ZIP. The other 165 files are byte-identical to build 1 |
