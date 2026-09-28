"""Boundary fixtures for the reconciliation's money thresholds (Codex QA-03).

Runs the real 01_schema.sql + 03_reconciliation.sql against a scratch database
(jsb_recon_fixture) holding hand-made rows at the 0.01 / 0.02 / 0.03 boundaries,
and checks each lands in the right category:
  * any fee difference of 1 cent or more is a fee break (the contract is exact);
  * a gross difference of exactly 1 cent is rounding; 2 or 3 cents is a gross break;
  * a net that is 1 cent off gross - fee is a net break.
Also checks the dbt model and the independent pandas check use the same thresholds.

Connection from env: DB_HOST (127.0.0.1), DB_PORT (3306), DB_SOCKET, DB_USER (assess),
DB_PASSWORD. Usage: python 06_threshold_fixtures.py
"""
import os
import re
import sys
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DB = "jsb_recon_fixture"

# (ref, deposit amount, gross, fee, net, expected category prefix)
FIXTURES = [
    ("FX-F00", 100.00, 100.00, 3.00, 97.00, "OK"),
    ("FX-F01", 100.00, 100.00, 3.01, 96.99, "BREAK: settled fee differs"),
    ("FX-F02", 100.00, 100.00, 3.02, 96.98, "BREAK: settled fee differs"),
    ("FX-F03", 100.00, 100.00, 3.03, 96.97, "BREAK: settled fee differs"),
    ("FX-G01", 100.00, 99.99, 3.00, 96.99, "NOT A PROBLEM: rounding"),
    ("FX-G02", 100.00, 99.98, 3.00, 96.98, "BREAK: settled gross amount differs"),
    ("FX-G03", 100.00, 99.97, 3.00, 96.97, "BREAK: settled gross amount differs"),
    ("FX-N01", 100.00, 100.00, 3.00, 96.99, "BREAK: net amount is not gross minus fee"),
]


def statements(sql):
    sql = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in sql.split(";") if s.strip()]


def main():
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
        unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
        password=os.environ.get("DB_PASSWORD", "AssessPass123!"), autocommit=True)
    cur = conn.cursor()
    schema = (HERE / "01_schema.sql").read_text().replace("jsb_assessment", DB)
    for s in statements(schema):
        cur.execute(s)
    for i, (ref, amt, gross, fee, net, _) in enumerate(FIXTURES, 1):
        cur.execute("INSERT INTO internal_deposits (deposit_id, player_id, created_at, amount, currency, "
                    "method, gateway_ref, status) VALUES (%s,'PFX','2026-09-03 10:00:00',%s,'NAD','card',%s,'SUCCESS')",
                    (f"DFX{i:03d}", amt, ref))
        cur.execute("INSERT INTO gateway_settlement (gateway_txn_id, merchant_ref, settled_at, gross_amount, fee, "
                    "net_amount, currency, status) VALUES (%s,%s,'2026-09-03 10:30:00',%s,%s,%s,'NAD','SETTLED')",
                    (f"GFX{i:03d}", ref, gross, fee, net))
    recon = (HERE / "03_reconciliation.sql").read_text().replace("jsb_assessment", DB)
    for s in statements(recon):
        cur.execute(s)
        if cur.description:
            cur.fetchall()
    cur.execute(f"SELECT gateway_ref, category FROM {DB}.recon_exceptions")
    got = dict(cur.fetchall())

    failures = 0
    for ref, amt, gross, fee, net, expected in FIXTURES:
        ok = got.get(ref, "").startswith(expected)
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {ref}: deposit {amt:.2f} gross {gross:.2f} fee {fee:.2f} "
              f"net {net:.2f} -> {got.get(ref)}")

    # the other two implementations must use the same thresholds
    dbt = (ROOT / "dbt_jsb_assessment/models/marts/fct_recon_exceptions.sql").read_text()
    pandas_check = (HERE / "04_independent_check.py").read_text()
    for name, text, needles in [
        ("dbt model", dbt, ["1.00, 2)) > 0.005", "gross_amount) > 0.015", "between 0.005 and 0.015"]),
        ("pandas check", pandas_check, ["exp_fee) > 0.005", "diff > 0.015", "diff >= 0.005"]),
    ]:
        missing = [n for n in needles if n not in text]
        failures += bool(missing)
        print(f"{'PASS' if not missing else 'FAIL'}  {name} uses the same thresholds"
              + (f" (missing: {missing})" if missing else ""))
    print("ALL BOUNDARY FIXTURES PASS" if not failures else f"{failures} FAILURE(S)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
