# JSB Assessment: Power BI package

Everything Power BI Desktop needs to open and refresh the report, plus the exported tables and a
checklist of expected values. The build scripts are in the repository (`powerbi/`), not in this
package.

## Open it
1. **Close Power BI Desktop.** If an older `JSB_Assessment` is open, it can hold on to old data.
2. **Unzip this package into a new, empty folder.** Don't unzip it over an older copy.
3. Open `JSB_Assessment.pbip` in Power BI Desktop, then click **Home → Refresh**.
4. Check each page against `expected_values.md`.

**Quick check that you have the current version:** Page 1 shows GGR **260.00**, Bonus Cost
**40.00**, NGR **220.00**, Liability **10.00** and **18.18%** in the campaign table, and Page 4 shows
**4** ingestion runs. GGR −70.00, NGR −90.00 or 3 runs means an old copy is open.

## Contents
| Path | What it is |
|---|---|
| `JSB_Assessment.pbip` | The file you open |
| `JSB_Assessment.SemanticModel/` | The model: 11 tables with their data embedded, 7 relationships, 28 DAX measures |
| `JSB_Assessment.Report/` | The four report pages and the theme |
| `data/*.csv` | The same 11 tables as plain CSV exports of the dbt marts. The report doesn't read these; they are the exported tables, for inspection |
| `expected_values.md` | What every visual should show after a refresh |

The data is embedded in the model, so no folder path or database connection is needed. The
embedded tables are byte-for-byte the same as `data/*.csv`, and this was checked before packaging.
Provenance (source commit, SHA-256 and per-file hashes) is in the repository at
`candidate-assessment/evidence/POWERBI_PACKAGE.md`.
