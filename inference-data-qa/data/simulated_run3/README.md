# Simulated third delivery (for the incremental demo only)

**Not supplied data.** These are copies of the three supplied extracts with a few deliberate edits, so the
incremental run can show issues being resolved and a new one being raised. Nothing in the main analysis
uses this folder.

| File | Edit | Expected effect |
|---|---|---|
| HR_Source.csv | E1020 department filled in as Finance | DQ02 and RC04 resolve for E1020 |
| HR_Source.csv | E1045 manager changed to E9998, which does not exist | **New** DQ03 and RC04 issues for E1045 (the alerts) |
| Payroll_Source.csv | E1029 set to Stopped | DQ04 resolves for E1029 |
| Payroll_Source.csv | Second E1015 row (58,600) removed | DQ01 and RC03 resolve for E1015 |
| Employee_360.csv | E1027 added, E1099 removed, E1012 set to Terminated | RC01, RC02 and RC03 (E1012) resolve |
