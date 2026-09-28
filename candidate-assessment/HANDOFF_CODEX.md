# Handoff: Claude → Codex

Branch: `claude/sleepy-hawking-uiq0u9` · folder: `candidate-assessment/`

**Roles:** Claude builds; Codex verifies.

**How we talk:** Codex writes its findings to `candidate-assessment/CODEX_REVIEW.md` on this branch and pushes. Claude pulls it, fixes each item or answers why not, and replies under each finding in the same file. Codex re-checks and marks each item `VERIFIED` or `STILL FAILING`. Keep each finding to one issue with the exact command or visual and the expected vs actual value.

## What is done

| Area | State | Evidence |
|---|---|---|
| Ex 1 reconciliation | 274 of 306 settlements match exactly. 12 exception types. The bridge R218,280.00 → R217,979.97 leaves R0.00 unexplained. The MySQL script, the dbt model and an independent pandas version agree on all 317 rows and every category. | `exercise1-reconciliation/summary.md`, `sql/04_independent_check.py`, `screenshots/02_three_way_agreement.png` |
| Ex 2 ingestion | Killed mid-page and restarted: 0 duplicates, 0 missing rows. A 429 is retried. 1 bad record is quarantined. 1,024 rows after the provider update. | `exercise2-ingestion/evidence/run_transcript.txt` |
| Ex 3 schema | 23 tables. The 4 required queries return the right results. | `exercise3-schema-design/` |
| dbt | `dbt build`: 67/67 pass (23 models, 44 tests), re-run on MariaDB 10.11 after the QA fixes | `dbt_jsb_assessment/evidence/dbt_build_output.txt` |
| Power BI | 11 tables, 7 relationships, 20 measures, 4 pages. The data is embedded. The user opened the previous build in Desktop: all 4 pages rendered. This build adds the tile colours, a navy title banner, a grey page background, short category labels, the waterfall axis starting at 205,000, and status colours. | `powerbi/`, `powerbi/expected_values.md` |
| Local database | `local_load/00_drop_other_build_tables.sql` drops the 45 tables another build left in `jsb_assessment`. `01_load_submission_tables.sql` loads this submission's 29 tables (re-running drops and reloads them). Tested on MariaDB 10.11: the reconciliation re-runs to 274 matched and 317 rows. | `local_load/README.md` |
| Write-up | `JSB_Candidate_Submission.docx` / `.pdf`, 16 pages | top-level folder |

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
4. **dbt (optional):** with the database loaded, `cd dbt_jsb_assessment && dbt build` → 67/67.

Please don't restructure or rename things. Report findings; small, obviously correct fixes may be committed, with a line in `CODEX_REVIEW.md` saying what changed.
