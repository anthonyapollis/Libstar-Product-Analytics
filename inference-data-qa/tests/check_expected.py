"""Independent check of the Spark results, in plain Python (no Spark, no pandas).

Recomputes the affected employee IDs for every rule straight from the CSVs, with separately written
logic, and compares them with outputs/monitoring.csv from run_local.py (or a Databricks export).
Runs in seconds, so it is cheap enough for every pull request.

    python tests/check_expected.py
"""
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AS_OF, SNAPSHOT_END = date(2026, 10, 8), date(2026, 10, 31)


def read(name):
    with open(ROOT / "data" / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def d(s):
    return date(*map(int, s.replace("/", "-").split("-")))


hr, pay, e360 = read("HR_Source.csv"), read("Payroll_Source.csv"), read("Employee_360.csv")
H = {r["employee_id"]: r for r in hr}
E = {r["employee_id"]: r for r in e360}
P = {}
for r in pay:
    P.setdefault(r["employee_id"], []).append(r)
loc = lambda v: "Cape Town" if v.strip().upper() in ("CPT", "CAPE TOWN") else v.strip()  # noqa: E731

expected = {}
expected["DQ01"] = {k for k, v in P.items() if len(v) > 1} | {k for k in H if sum(r["employee_id"] == k for r in hr) > 1}
managers = {r["manager_id"] for r in hr if r["manager_id"]}
expected["DQ02"] = {k for k, r in H.items()
                    if any(not r[c].strip() for c in ("full_name", "email", "department", "location", "employment_status", "effective_date"))
                    or (not r["manager_id"] and k not in managers)}
expected["DQ03"] = {k for k, r in list(H.items()) + list(E.items()) if r["manager_id"] and r["manager_id"] not in H}
expected["DQ04"] = set()
for k, r in H.items():
    statuses = {p["payroll_status"] for p in P.get(k, [])}
    if not statuses or (r["employment_status"] == "Terminated" and statuses != {"Stopped"}) \
            or (r["employment_status"] == "Active" and statuses != {"Payable"}):
        expected["DQ04"].add(k)
expected["DQ05"] = {r["employee_id"] for r in pay if r["currency"] != "ZAR" or float(r["monthly_salary_zar"] or 0) <= 0}
stale = AS_OF - timedelta(days=30)
expected["DQ06"] = {r["employee_id"] for r in hr + pay + e360 if d(r["last_updated"]) < stale}
expected["RC01"] = set(H) - set(E)
expected["RC02"] = set(E) - set(H)
rc03, rc04 = set(), set()
for k in set(H) & set(E):
    h, e, p = H[k], E[k], P.get(k, [])
    if h["employment_status"] != e["employment_status"]:
        rc03.add(k)
    salaries = {float(x["monthly_salary_zar"]) for x in p}
    currencies = {x["currency"] for x in p}
    if len(salaries) != 1 or float(e["monthly_salary_zar"]) not in salaries or currencies != {e["currency"]}:
        rc03.add(k)  # no payroll record, conflicting payroll values, or a different value
    if (h["department"] != e["department"] or h["manager_id"] != e["manager_id"]
            or loc(h["location"]) != loc(e["location"]) or h["full_name"] != e["full_name"]):
        rc04.add(k)
expected["RC03"], expected["RC04"] = rc03, rc04

with open(ROOT / "outputs" / "monitoring.csv", newline="", encoding="utf-8") as f:
    actual = {r["rule_id"]: {x for x in r["affected_ids"].split(", ") if x} for r in csv.DictReader(f)}

bad = 0
for rule in sorted(expected):
    ok = expected[rule] == actual.get(rule)
    bad += not ok
    print(f"{'OK  ' if ok else 'DIFF'} {rule}: expected {sorted(expected[rule])}" + ("" if ok else f", Spark {sorted(actual.get(rule, []))}"))
print(f"\n{len(expected) - bad}/{len(expected)} rules agree with the independent calculation")
sys.exit(1 if bad else 0)
