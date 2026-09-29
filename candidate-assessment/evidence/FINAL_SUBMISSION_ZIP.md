# Final submission ZIP: provenance

| Item | Value |
|---|---|
| File | `deliverables/JSB_Candidate_Submission_Final.zip` (committed on branch `claude/sleepy-hawking-uiq0u9`) |
| SHA-256 | `6c5ecc40d7739f2634d733041f85110f6d2126205bd5d1800eeb50724614d8d2` |
| Size | 6,185,577 bytes |
| Files | 167: 166 content files + `MANIFEST.sha256` (all under `JSB_Candidate_Submission/`) |
| Source commit | `a6543562c4c6efe8fe58d809dfc7bc348609fe89` |
| Built by | `python submission_build/build_final_zip.py a654356` (`git archive` of `candidate-assessment/`, repository-only files removed, fixed timestamps) |
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
