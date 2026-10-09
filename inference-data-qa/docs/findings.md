# Findings, reconciliation and root cause

Reporting snapshot: October 2026. Extract date: 2026-10-08 (the newest `last_updated` in any file).
Every number below comes from `outputs/` (produced by `run_local.py`) and is re-derived independently by
`tests/check_expected.py`.

## 1. Profile (`sql/01_profile.sql`, `outputs/profile_*.csv`)

| | HR | Payroll | Employee 360 |
|---|---:|---:|---:|
| Rows | 48 | 48 | 48 |
| Distinct employee_id | 48 | **47** (E1015 twice) | 48 |
| IDs that are also in HR | 48 | 47 (E1044 missing) | **47** (E1027 missing, E1099 extra) |
| Blank values | department 1, email 1, manager 5 | none | manager 5 |
| Oldest `last_updated` | 2026-07-01 (E1030) | 2026-10-07 | 2026-07-02 (E1030) |

**Unexpected patterns and freshness concerns:**
- **Payroll covers September (`pay_period` 2026-09) for an October snapshot.** The salary in Employee 360 is
  therefore last month's. This is acceptable if documented, but it matters for leavers (see finding 2).
- **E1030** has not been updated for 99 days in HR and 98 days in Employee 360.
- **HR dates use `yyyy/MM/dd`**, while the other files use ISO dates. A loader that assumes ISO dates would turn
  every HR date into NULL.
- **Payroll E1037 is USD in a column named `monthly_salary_zar`.** Employee 360 shows the same number labelled ZAR.

**Differences that are not errors (judgement):**
- **CPT and Cape Town (E1040).** These are the same place, so the comparison uses the standard name.
- **E1042 HR effective date of 19 Nov.** This is a future-dated change. Employee 360 correctly keeps the
  value in force in October.
- **Blank manager for E1001–E1005.** They head departments and manage others; the rule allows this.
- **HR `last_updated` before `effective_date` (23 rows).** These are changes keyed in before they take effect, which is normal.

## 2. Top three findings

**1. Employee 360 is wrong in ways that row counts and totals cannot see. This blocks release.**
All three files have 48 rows, but:
- **Wrong people:** E1027 (Tumi Mbatha, active, paid R80,300) is missing, and E1099 "Unknown Legacy Employee" is there instead.
- **Wrong status:** E1012 is shown Active although HR terminated them and payroll has stopped them.
- **Wrong salaries:** E1018's salary is R69,400 against payroll's R62,900. E1044 shows a salary although payroll has no record for them.
- **Wrong currency:** E1037's USD amount is relabelled ZAR.

*Business significance:* Employee 360 shows **46 active employees against HR's 45**, and its salary
total is **R64,600 above payroll**. That net figure hides **R225,200 of gross differences across four employees**,
which partly cancel out. Headcount and people-cost reporting built on it is wrong for specific named employees.

**2. A leaver is still payable (E1029). Alert payroll before the October cut-off.**
- HR terminated E1029 effective 2026-10-02, but payroll still has them as **Payable** (R84,200 a month).
- The other two October leavers (E1012 from 6 Oct and E1041 from 7 Oct) are both **Stopped**, although they left later.

*Caveat (judgement):* the payroll period is September, and September pay may be legitimately due. The proven
fact is that the leaver treatment is inconsistent. The risk is an October overpayment and its recovery.

E1044 is the mirror case: active in HR with **no payroll record at all**, so they may be unpaid.

**3. Payroll, the salary system of record, has integrity defects.**
- **E1015 appears twice** with different salaries (R57,100 and R58,600). Employee 360 took the first, but nobody
  can say which salary is correct.
- **E1037 is in USD** in a ZAR-only field.

*Business significance:* until payroll is fixed, salary in Employee 360 cannot be verified for these
employees, whatever value it shows.

**Lower priority:**
- E1024's manager is **E9999**, who doesn't exist. This breaks org charts and approval routing.
- **Blanks in HR:** E1020 has no department (Employee 360 shows Finance from elsewhere) and E1035 has no email.
- **E1033** is People in HR but Sales in Employee 360.

## 3. Reconciliation summary (`sql/03_reconciliation.sql`, `reconcile_fields` in the notebook)

| Measure | Value |
|---|---:|
| Employees in HR (system of record) | 48 |
| Rows in Employee 360 | 48 |
| Matched on employee_id | 47 |
| Missing downstream | 1 (E1027) |
| Unexpected downstream | 1 (E1099) |
| Matched employees with a field error | 6 (E1012, E1018, E1020, E1033, E1037, E1044) |
| Matched employees whose value cannot be verified | 1 (E1015) |
| Field differences that are legitimate exceptions | 1 (E1042, future-dated) |

**Why agreeing totals prove nothing here:**
- **Row counts:** all three files have 48 rows (R2), yet one employee is missing and one is invented.
- **Salary total:** the net difference is R64,600, but it is made of +R82,200 (E1099) −R80,300 (E1027)
  +R56,200 (E1044) +R6,500 (E1018), which is R225,200 gross (R3).
- **Headcount:** a missing employee and an invented one cancel exactly. Only a key-level and field-level
  comparison against the system of record finds them.

## 4. Root-cause diagnosis: E1099 appears and E1027 disappears

**Proven facts (evidence in `outputs/`):**
1. **E1027 is missing downstream.** E1027 is in HR (Active, Technology, Durban) and in payroll (Payable, R80,300),
   but not in Employee 360 (`recon_keys.csv`).
2. **E1099 exists only downstream.** "Unknown Legacy Employee" is in Employee 360 only, not in HR or payroll.
3. **E1099 is a copy of E1028.** It is identical to E1028 (Isabella Ross) on **all 8 non-key attributes**:
   department, location, manager, status, salary R82,200, currency, effective date and last updated
   (`recon_lookalike.csv`).
4. **The current build wrote it.** E1099's `last_updated` (2026-10-08) is the build date that Employee 360 stamps
   on all but one row. HR's own dates vary from 1 to 8 October.
5. **The count check could not catch it.** The row count is unchanged at 48.

**Likely point of failure (hypothesis, not proven):**
- **Most likely:** the identity-resolution / master-data step that assigns `employee_id` in the Employee 360 build.
  A legacy-ID cross-reference (crosswalk) entry appears to have produced a second record carrying E1028's
  attributes under the legacy key E1099.
- **Possible link:** the same step may be why E1027, the neighbouring ID, was dropped.
- **Alternative:** a manual "legacy employee" insert that copied an existing row, alongside a separate filter that
  excluded E1027.

**Related pattern (hypothesis):**
- **Employee 360 holds values the current extracts do not contain:** E1020's department, E1044's salary, and
  E1012's status from before termination.
- **Likely mechanism:** the build may keep the previous value when the source is blank or missing, or read
  from an older snapshot.

**What would confirm it:**
- the cross-reference / MDM table entries for E1027, E1028 and E1099;
- Delta history (`DESCRIBE HISTORY` and `VERSION AS OF`) of the Employee 360 table, to see when E1099 first
  appeared and E1027 disappeared;
- the 2026-10-08 job run logs and the merge logic of the Employee 360 build;
- HR confirming that no employee E1099 exists.

**Business impact:**
- **People reporting:** the people listed are wrong (one real employee absent, one invented), while headcount
  and cost look plausible.
- **Downstream systems:** any system fed by Employee 360, such as access provisioning or org charts, inherits
  the error.

**Best placed to fix:**
- **The Employee 360 data engineering team**, who own the build and the crosswalk.
- **The MDM / HR data steward**, who confirms the correct identities.
- Release stays blocked by RC01 and RC02 until fixed.

## 5. Monitoring output (`outputs/monitoring.csv`)

| Rule | Dimension | Status | Affected | Severity | Action | Affected IDs |
|---|---|---|---:|---|---|---|
| DQ01 employee_id unique | Uniqueness | FAIL | 1 | Critical | Block release | E1015 |
| DQ02 mandatory HR fields | Completeness | FAIL | 2 | Medium | Monitor (alert > 1) | E1020, E1035 |
| DQ03 manager exists | Referential integrity | FAIL | 1 | High | Alert now | E1024 |
| DQ04 HR status = payroll status | Consistency | FAIL | 2 | Critical | Alert now | E1029, E1044 |
| DQ05 positive ZAR salary | Validity | FAIL | 1 | High | Block release | E1037 |
| DQ06 updated within 30 days | Freshness | FAIL | 1 | Medium | Monitor (alert > 2) | E1030 |
| RC01 HR employee in Employee 360 | Reconciliation | FAIL | 1 | Critical | Block release | E1027 |
| RC02 no record without HR employee | Reconciliation | FAIL | 1 | Critical | Block release | E1099 |
| RC03 status, salary, currency match | Reconciliation | FAIL | 5 | Critical | Block release | E1012, E1015, E1018, E1037, E1044 |
| RC04 department, manager, location, name | Reconciliation | FAIL | 2 | High | Alert now | E1020, E1033 |

**What the actions mean:**
- **Block release:** any failure stops this Employee 360 build from being published. These are wrong people,
  wrong pay or unverifiable pay.
- **Alert now:** the owner hears the same day, but publishing may continue, because the fix sits in a source
  system. DQ04 (a leaver still payable) goes to payroll before the pay-run cut-off.
- **Monitor:** results are trended, with an alert only above the threshold. Example threshold: alert when more
  than 1 employee (2% of 48) has a blank mandatory field.

Decision for this delivery: **BLOCK** (DQ01, DQ05, RC01, RC02 and RC03).
