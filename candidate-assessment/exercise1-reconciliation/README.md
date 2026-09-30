# Exercise 1: payment gateway reconciliation

## Deliverables
| Brief asks for | File |
|---|---|
| Exceptions list with a category and an explanation per row | `exceptions.csv`: 49 rows (34 genuine breaks, 6 timing differences, 9 not a problem) |
| Spreadsheet version, with formulas | `Reconciliation_Workbook.xlsx`: Summary (bridge and category totals as `SUMIFS`/`COUNTIFS`), Assumptions, Exceptions, and both raw files |
| One-page Finance Manager summary with the bridge | `Finance_Summary.pdf` |
| Categories, cause, impact, next step, owner; automation and alerts; assumptions | `summary.md` |
| Code | `sql/` (below), and the same rules as a dbt model: `../dbt_jsb_assessment/models/marts/fct_recon_exceptions.sql` |

## Reproduce
MariaDB 10.4+ (run on 10.11 and on 10.4 under XAMPP); the SQL is MySQL-compatible. Set `DB_HOST`, `DB_PORT`, `DB_USER` and `DB_PASSWORD` if they differ from
the defaults in the scripts. Run from `sql/`:

```bash
mysql -u <user> -p < 01_schema.sql                    # tables for the two files, loaded as-is
python 02_load.py                                     # load both CSVs (326 + 306 rows)
mysql -u <user> -p jsb_assessment < 03_reconciliation.sql   # match, categorise, bridge -> recon_exceptions
python 07_export_exceptions.py                        # exceptions.csv + Reconciliation_Workbook.xlsx
python 04_independent_check.py                        # separate pandas implementation must agree row by row
python 06_threshold_fixtures.py                       # boundary tests at 1, 2 and 3 cents
python 05_agreement_chart.py                          # chart of the three-way agreement
```

`07_export_exceptions.py` refuses to write the files if the bridge doesn't reconcile to 0.00. To
export from the dbt model instead of the script's table, set
`RECON_TABLE=jsb_platform_marts.fct_recon_exceptions`.

## Checks behind the numbers
- **Three implementations agree.** The SQL script, the dbt model and an independent pandas version
  agree on all 317 rows and on every category's count and rand total. Evidence:
  `evidence/agreement_by_category.csv` and `screenshots/02_three_way_agreement.png`.
- **The bridge is exactly zero.** Its residual is 0.00 in SQL, in the export script, in the
  workbook's formulas, and in the dbt test `assert_recon_bridge_reconciles`.
- **Every threshold is tested.** `06_threshold_fixtures.py` checks each threshold at 1, 2 and 3
  cents, and that dbt and pandas use the same thresholds as the SQL.
