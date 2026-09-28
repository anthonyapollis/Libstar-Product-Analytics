"""Independent re-implementation of the categorisation in pandas, compared row by
row against the SQL result (recon_exceptions). Different code path, same rules:
if both agree on every (deposit, settlement, category) triple, neither has a logic slip.
Usage: python 04_independent_check.py
"""
import os
import re
import pandas as pd
import pymysql

d = pd.read_csv("../internal_deposits.csv", dtype=str)
g = pd.read_csv("../gateway_settlement.csv", dtype=str)
d["amount"] = d.amount.astype(float)
for c in ["gross_amount", "fee", "net_amount"]:
    g[c] = g[c].astype(float)
d["created_at"] = pd.to_datetime(d.created_at)
g["settled_at"] = pd.to_datetime(g.settled_at)
norm = lambda s: re.sub(r"[^A-Za-z0-9]", "", s).upper()
d["ref"], g["ref"] = d.gateway_ref.map(norm), g.merchant_ref.map(norm)
succ = d[d.status == "SUCCESS"]
succ_refs = succ.ref.value_counts()
gw_by_ref = {r: grp for r, grp in g.groupby("ref")}

out = set()
impact = {}   # (deposit_id, settlement key) -> rand impact, computed here, not read from SQL
for _, dep in succ.iterrows():
    rows = gw_by_ref.get(dep.ref)
    if succ_refs[dep.ref] > 1:
        cat = "dup_internal"
    elif rows is None:
        cat = "timing_next" if dep.created_at >= pd.Timestamp("2026-09-07 23:45") else "missing_settlement"
    elif len(rows) > 1:
        cat = "dup_gateway"
    else:
        r = rows.iloc[0]
        exp_fee = round(r.gross_amount * 0.02 + 1, 2)
        diff = abs(dep.amount - r.gross_amount)
        if r.status == "REVERSED":
            cat = "reversal"
        elif abs(r.fee - exp_fee) > 0.005:
            cat = "fee"
        elif abs(r.net_amount - (r.gross_amount - r.fee)) > 0.005:
            cat = "net"
        elif diff > 0.015:
            cat = "amount"
        elif diff >= 0.005:
            cat = "rounding"
        else:
            cat = "ok"
    if rows is None:
        out.add((dep.deposit_id, None, cat))
        impact[(dep.deposit_id, None)] = dep.amount
    else:
        for _, r in rows.iterrows():
            key = (dep.deposit_id, (r.gateway_txn_id, str(r.settled_at)))
            out.add((*key, cat))
            exp_fee = round(r.gross_amount * 0.02 + 1, 2)
            impact[key] = {"reversal": r.gross_amount, "fee": r.fee - exp_fee,
                           "net": (r.gross_amount - r.fee) - r.net_amount}.get(cat, dep.amount - r.gross_amount)

failed = d[d.status == "FAILED"].set_index("ref")
for _, r in g[~g.ref.isin(succ.ref)].iterrows():
    skey = (r.gateway_txn_id, str(r.settled_at))
    if r.ref in failed.index:
        key = (failed.loc[r.ref, "deposit_id"], skey); cat = "failed_but_settled"
    elif r.settled_at < pd.Timestamp("2026-09-01 00:15"):
        key = (None, skey); cat = "timing_prior"
    else:
        key = (None, skey); cat = "unrecognised"
    out.add((*key, cat))
    impact[key] = r.gross_amount

SQL_TO_SHORT = {
    "OK:": "ok", "BREAK: payment confirmed": "failed_but_settled", "BREAK: unrecognised": "unrecognised",
    "TIMING: prior-period": "timing_prior", "BREAK: duplicate internal": "dup_internal",
    "BREAK: duplicate gateway": "dup_gateway", "TIMING: settlement expected": "timing_next",
    "BREAK: deposit SUCCESS": "missing_settlement", "REVERSAL": "reversal",
    "BREAK: settled fee": "fee", "BREAK: net amount": "net", "BREAK: settled gross": "amount",
    "NOT A PROBLEM": "rounding",
}
conn = pymysql.connect(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
                       unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
                       password=os.environ.get("DB_PASSWORD", "AssessPass123!"), database="jsb_assessment")
sql = pd.read_sql("SELECT deposit_id, gateway_txn_id, settled_at, category FROM recon_exceptions", conn)
sql_set = set()
for _, r in sql.iterrows():
    short = next(v for k, v in SQL_TO_SHORT.items() if r.category.startswith(k))
    key = None if pd.isna(r.gateway_txn_id) else (r.gateway_txn_id, str(pd.Timestamp(r.settled_at)))
    sql_set.add((None if pd.isna(r.deposit_id) else r.deposit_id, key, short))

print(f"pandas rows: {len(out)}   SQL rows: {len(sql_set)}")
print(f"only in pandas: {sorted(map(str, out - sql_set))}")
print(f"only in SQL:    {sorted(map(str, sql_set - out))}")
print("AGREE on every row" if out == sql_set else "DISAGREE")

# ---- per-category agreement: MySQL script vs dbt model vs this independent pandas code ----
SHORT_TO_SQL = {v: k for k, v in SQL_TO_SHORT.items()}
pd_cat = pd.DataFrame([{"short": c, "impact": impact[(d_, g_)]} for d_, g_, c in out])
pd_agg = pd_cat.groupby("short").agg(n_pandas=("impact", "size"), rand_pandas=("impact", "sum"))
sql_agg = pd.read_sql("SELECT category, COUNT(*) n, SUM(financial_impact) v FROM recon_exceptions GROUP BY category", conn)
dbt_agg = pd.read_sql("SELECT category, n, impact_total v FROM jsb_platform_marts.mart_recon_summary_by_category", conn)
rows = []
for _, r in sql_agg.iterrows():
    short = next(v for k, v in SQL_TO_SHORT.items() if r.category.startswith(k))
    d = dbt_agg[dbt_agg.category == r.category].iloc[0]
    rows.append({"category": r.category, "short": short,
                 "n_sql": int(r.n), "n_dbt": int(d.n), "n_pandas": int(pd_agg.loc[short, "n_pandas"]),
                 "rand_sql": round(float(r.v), 2), "rand_dbt": round(float(d.v), 2),
                 "rand_pandas": round(float(pd_agg.loc[short, "rand_pandas"]), 2)})
agree = pd.DataFrame(rows).sort_values("n_sql", ascending=False)
agree["agree"] = ((agree.n_sql == agree.n_dbt) & (agree.n_dbt == agree.n_pandas)
                  & (agree.rand_sql == agree.rand_dbt) & (agree.rand_dbt == agree.rand_pandas))
agree.to_csv("../evidence/agreement_by_category.csv", index=False)
print(agree[["short", "n_sql", "n_dbt", "n_pandas", "rand_sql", "rand_dbt", "rand_pandas", "agree"]].to_string(index=False))
print("ALL 13 CATEGORIES AGREE (count and rand)" if agree.agree.all() else "MISMATCH")
