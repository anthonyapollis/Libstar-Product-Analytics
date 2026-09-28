"""Build the Exercise 1 deliverables from the reconciliation table:

  ../exceptions.csv                 every difference, one row each: classification (genuine break /
                                    timing difference / not a problem), category, a row-specific
                                    explanation, next step, owner, financial impact and bridge amount
  ../Reconciliation_Workbook.xlsx   the same rows plus the raw files, a category summary and the
                                    bridge, all as live formulas (SUMIFS/COUNTIFS) Finance can audit

Reads the table written by 03_reconciliation.sql (default) or the dbt model
(RECON_TABLE=jsb_platform_marts.fct_recon_exceptions). Both hold the same 317 rows.
Connection from env: DB_HOST (127.0.0.1), DB_PORT (3306), DB_SOCKET, DB_USER (assess), DB_PASSWORD.
Usage: python 07_export_exceptions.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pymysql

HERE = Path(__file__).resolve().parent
EX1 = HERE.parent
TABLE = os.environ.get("RECON_TABLE", "jsb_assessment.recon_exceptions")
PERIOD_START = pd.Timestamp("2026-09-01 00:00:00")
PERIOD_END = pd.Timestamp("2026-09-07 23:59:59")

GENUINE, TIMING, NOT_A_PROBLEM = "Genuine break", "Timing difference", "Not a problem"
FORMAT_CATEGORY = "NOT A PROBLEM: reference formatting differs (matched after normalising)"

# category -> (classification, bridge line, next step, owner)
CATEGORIES = {
    "BREAK: payment confirmed, wallet not credited": (
        GENUINE, "+ Settled by the gateway but marked FAILED by us",
        "Credit the player's wallet today; check the callback/webhook logs for the lost confirmation",
        "Payments engineering"),
    "BREAK: unrecognised settlement (no internal record)": (
        GENUINE, "+ Settlements with no internal record",
        "Ask the gateway for the transaction detail (payer, time, reference) before treating it as ours",
        "Payments + Finance"),
    "BREAK: net amount is not gross minus fee": (
        GENUINE, None, "Claim the short-paid amount; ask the gateway how net was calculated", "Finance"),
    "BREAK: settled fee differs from contracted fee": (
        GENUINE, None, "Raise a fee dispute citing the contract (2% of gross + 1.00)", "Finance"),
    "BREAK: settled gross amount differs from internal amount": (
        GENUINE, "+/- Gross amount differences with the gateway (net)",
        "Dispute with the gateway using the payment evidence; correct the wallet once agreed", "Finance"),
    "BREAK: duplicate gateway settlement for one reference (double-credit risk)": (
        GENUINE, "+ Duplicate gateway settlement rows",
        "Confirm with the gateway whether money moved twice or only the report repeated", "Payments engineering"),
    "BREAK: duplicate internal SUCCESS deposit for one settlement (double-credit risk)": (
        GENUINE, "- Duplicate internal deposit rows",
        "Check whether the wallet was credited twice and reverse the extra credit; add an idempotency key",
        "Engineering"),
    "REVERSAL: gateway reversed/charged back after settlement": (
        GENUINE, "- Reversals / chargebacks",
        "Confirm the matching wallet debit was posted; if not, claw back", "Finance"),
    "BREAK: deposit SUCCESS, no gateway settlement found": (
        GENUINE, "- Deposits with no settlement yet (mid-week)",
        "Re-check the next settlement file; escalate to the gateway if still missing after 3 days", "Finance"),
    "TIMING: settlement expected in next period (created near cut-off)": (
        TIMING, "- Created in the last 15 min, not yet settled (provisional)",
        "Match against the 8-14 Sep settlement file; if missing, reclassify as a break", "Finance"),
    "TIMING: prior-period deposit settled at start of period": (
        TIMING, "+ Settled in the first 15 min, no deposit this week (provisional)",
        "Match against the 25-31 Aug internal file; if missing, reclassify as unrecognised", "Finance"),
    "NOT A PROBLEM: rounding difference <= 1 cent": (
        NOT_A_PROBLEM, "+/- Rounding (exactly 1 cent)", "None; Finance to confirm 1 cent is immaterial", "Finance"),
    FORMAT_CATEGORY: (
        NOT_A_PROBLEM, None, "Ask the gateway to return our reference verbatim", "Payments engineering"),
}
BRIDGE_LINES = [  # order of the bridge, internal total -> gateway total
    "- Duplicate internal deposit rows", "- Reversals / chargebacks",
    "- Deposits with no settlement yet (mid-week)",
    "- Created in the last 15 min, not yet settled (provisional)",
    "+ Settled in the first 15 min, no deposit this week (provisional)",
    "+ Settlements with no internal record", "+ Settled by the gateway but marked FAILED by us",
    "+ Duplicate gateway settlement rows", "+/- Gross amount differences with the gateway (net)",
    "+/- Rounding (exactly 1 cent)",
]


def money(v):
    return f"{v:,.2f}"


def norm(ref):
    return "".join(ch for ch in str(ref) if ch.isalnum()).upper()


def load():
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
        unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
        password=os.environ.get("DB_PASSWORD", "AssessPass123!"))
    cols = ("deposit_id, player_id, created_at, dep_amount, gateway_ref, gateway_txn_id, merchant_ref, "
            "settled_at, gross_amount, fee, net_amount, gw_status, expected_fee, category, financial_impact")
    df = pd.read_sql(f"SELECT {cols} FROM {TABLE}", conn)
    conn.close()
    for c in ("dep_amount", "gross_amount", "fee", "net_amount", "expected_fee", "financial_impact"):
        df[c] = pd.to_numeric(df[c]).astype(float)
    for c in ("created_at", "settled_at"):
        df[c] = pd.to_datetime(df[c])
    return df


def explain(r, ctx):
    c, g, d = r.category, r.gross_amount, r.dep_amount
    if c.startswith("BREAK: payment confirmed"):
        return (f"We marked {r.deposit_id} FAILED, but the gateway settled {money(g)} for {r.merchant_ref} "
                f"({r.gateway_txn_id}) at {r.settled_at}. The player paid and was not credited: we owe {money(g)}.")
    if c.startswith("BREAK: unrecognised"):
        hours = (r.settled_at - PERIOD_START).total_seconds() / 3600
        return (f"The gateway settled {money(g)} for {r.merchant_ref} ({r.gateway_txn_id}) at {r.settled_at}, "
                f"{hours:.0f} h into the period, too late to be a prior-period deposit (longest lag "
                f"{ctx['max_lag']}). No deposit on our side carries this reference, not even a failed one.")
    if c.startswith("BREAK: net amount"):
        return (f"Net {money(r.net_amount)} is not gross {money(g)} minus fee {money(r.fee)} = "
                f"{money(g - r.fee)}. Short-paid by {money(g - r.fee - r.net_amount)}.")
    if c.startswith("BREAK: settled fee"):
        return (f"Fee {money(r.fee)} vs contract {money(r.expected_fee)} (2% of {money(g)} + 1.00). "
                f"Overcharged {money(r.fee - r.expected_fee)}.")
    if c.startswith("BREAK: settled gross"):
        diff = g - d
        who = (f"the player paid {money(diff)} more than we credited (under-credited)" if diff > 0
               else f"we credited {money(-diff)} more than the gateway settled (over-credited)")
        return f"We recorded {money(d)}; the gateway settled {money(g)} ({diff:+,.2f}): {who}."
    if c.startswith("BREAK: duplicate gateway"):
        grp = ctx["gw_groups"][r.gateway_txn_id]
        times = ", ".join(str(t) for t in grp)
        first = r.settled_at == grp[0]
        return (f"{r.gateway_txn_id} for {r.merchant_ref} appears {len(grp)} times in the settlement file "
                f"(settled {times}). This row is the " + ("original." if first else
                f"repeat: it adds {money(g)} to the gateway total without a second deposit."))
    if c.startswith("BREAK: duplicate internal"):
        grp = ctx["dep_groups"][norm(r.gateway_ref)]
        ids = " and ".join(i for i, _ in grp)
        gap = int((grp[-1][1] - grp[0][1]).total_seconds())
        first = r.deposit_id == grp[0][0]
        return (f"{ids} are both SUCCESS for reference {r.gateway_ref}, created {gap} s apart, but the gateway "
                f"settled once ({money(g)}). This row is the " + ("original." if first else
                f"repeat. Only SUCCESS deposits credit a wallet, so the player was credited {money(d)} twice for one "
                f"payment: {money(d)} with no money behind it."))
    if c.startswith("REVERSAL"):
        return (f"The gateway reversed {money(g)} (settlement row {r.gateway_txn_id}, settled_at {r.settled_at}, "
                f"status REVERSED, e.g. a chargeback). {r.deposit_id} is still SUCCESS on our side and credited the "
                f"wallet, so unless a matching debit was posted we are {money(g)} out.")
    if c.startswith("BREAK: deposit SUCCESS, no gateway"):
        hours = (PERIOD_END - r.created_at).total_seconds() / 3600
        return (f"{r.deposit_id} for {money(d)}, created {r.created_at}, is SUCCESS on our side but has no settlement "
                f"{hours:.0f} h later at period end, far beyond the longest settlement lag seen this week "
                f"({ctx['max_lag']}).")
    if c.startswith("TIMING: settlement expected"):
        mins = (PERIOD_END - r.created_at).total_seconds() / 60
        return (f"{r.deposit_id} for {money(d)} was created at {r.created_at}, {mins:.0f} min before the period "
                f"cut-off. With a median settlement lag of {ctx['median_lag']}, it should settle in next week's "
                f"file (provisional until matched).")
    if c.startswith("TIMING: prior-period"):
        mins = (r.settled_at - PERIOD_START).total_seconds() / 60
        return (f"The gateway settled {money(g)} for {r.merchant_ref} at {r.settled_at}, {mins:.0f} min into the "
                f"period. The reference is not in this week's deposits: most likely a deposit created just before "
                f"midnight on 31 Aug (provisional until matched in last week's file).")
    if c.startswith("NOT A PROBLEM: rounding"):
        return (f"We recorded {money(d)}; the gateway settled {money(g)} ({g - d:+,.2f}). A 1-cent rounding "
                f"difference: immaterial.")
    if c == FORMAT_CATEGORY:
        return (f"We sent '{r.gateway_ref}'; the gateway returned '{r.merchant_ref}'. The same reference once case, "
                f"spaces and punctuation are ignored, so it matched and amounts agree.")
    raise ValueError(f"no explanation for category {c}")


def bridge_amount(r, ctx):
    """This row's contribution to the gross bridge from the internal total to the gateway total."""
    c = r.category
    if c.startswith(("BREAK: settled gross", "NOT A PROBLEM: rounding")):
        return round(r.gross_amount - r.dep_amount, 2)
    if c.startswith(("REVERSAL", "BREAK: deposit SUCCESS, no gateway", "TIMING: settlement expected")):
        return -r.dep_amount
    if c.startswith(("TIMING: prior-period", "BREAK: unrecognised", "BREAK: payment confirmed")):
        return r.gross_amount
    if c.startswith("BREAK: duplicate gateway"):
        return 0.0 if r.settled_at == ctx["gw_groups"][r.gateway_txn_id][0] else r.gross_amount
    if c.startswith("BREAK: duplicate internal"):
        return 0.0 if r.deposit_id == ctx["dep_groups"][norm(r.gateway_ref)][0][0] else -r.dep_amount
    return 0.0          # fee, net and formatting differences don't move gross


def build(df):
    ok = df[df.category.str.startswith("OK")]
    # lag of real settlements; duplicate repeats are excluded (they are re-reports, not a lag)
    lag = (ok.settled_at - ok.created_at).dt.total_seconds() / 60
    fmt = lambda m: f"{int(m // 60)} h {int(m % 60)} min" if m >= 60 else f"{m:.0f} min"
    ctx = {"median_lag": fmt(lag.median()), "max_lag": fmt(lag.max())}
    gw = df[df.category.str.startswith("BREAK: duplicate gateway")]
    ctx["gw_groups"] = {k: sorted(v.settled_at) for k, v in gw.groupby("gateway_txn_id")}
    dep = df[df.category.str.startswith("BREAK: duplicate internal")]
    ctx["dep_groups"] = {k: sorted(zip(v.deposit_id, v.created_at), key=lambda t: t[1])
                         for k, v in dep.groupby(dep.gateway_ref.map(norm))}

    exc = df[~df.category.str.startswith("OK")].copy()
    # matched rows whose reference text differs: a difference, but not a problem
    fmt_rows = ok[ok.gateway_ref != ok.merchant_ref].copy()
    fmt_rows["category"] = FORMAT_CATEGORY
    fmt_rows["financial_impact"] = 0.0
    rows = pd.concat([exc, fmt_rows], ignore_index=True)
    rows["classification"] = rows.category.map(lambda c: CATEGORIES[c][0])
    rows["explanation"] = rows.apply(lambda r: explain(r, ctx), axis=1)
    # an exception row that also has a formatting difference gets a note, not a second row
    also = (rows.category != FORMAT_CATEGORY) & rows.merchant_ref.notna() & rows.gateway_ref.notna() \
        & (rows.gateway_ref != rows.merchant_ref)
    rows.loc[also, "explanation"] += (" (The gateway also returned the reference as '"
                                      + rows.loc[also, "merchant_ref"] + "'.)")
    rows["next_step"] = rows.category.map(lambda c: CATEGORIES[c][2])
    rows["owner"] = rows.category.map(lambda c: CATEGORIES[c][3])
    rows["bridge_line"] = rows.category.map(lambda c: CATEGORIES[c][1] or "")
    rows["bridge_amount"] = rows.apply(lambda r: bridge_amount(r, ctx), axis=1)
    order = {GENUINE: 0, TIMING: 1, NOT_A_PROBLEM: 2}
    rows = rows.sort_values(["classification", "category", "created_at", "settled_at"],
                            key=lambda s: s.map(order) if s.name == "classification" else s).reset_index(drop=True)
    rows.insert(0, "exception_id", [f"E{i:03d}" for i in range(1, len(rows) + 1)])
    return rows, ctx


COLUMNS = ["exception_id", "classification", "category", "explanation", "next_step", "owner",
           "financial_impact", "bridge_line", "bridge_amount", "deposit_id", "player_id", "created_at",
           "dep_amount", "gateway_ref", "gateway_txn_id", "merchant_ref", "settled_at", "gross_amount",
           "fee", "expected_fee", "net_amount", "gw_status"]


def main():
    df = load()
    rows, ctx = build(df)
    dep = pd.read_csv(EX1 / "internal_deposits.csv")
    gw = pd.read_csv(EX1 / "gateway_settlement.csv")
    internal = dep[dep.status == "SUCCESS"].amount.sum()
    gateway = gw[gw.status == "SETTLED"].gross_amount.sum()
    residual = round(gateway - internal - rows.bridge_amount.sum(), 2) + 0.0   # + 0.0: no "-0.00"
    if residual != 0:
        sys.exit(f"bridge does not reconcile: residual {residual}")
    out = rows[COLUMNS].copy()
    for c in ("created_at", "settled_at"):
        out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    out.to_csv(EX1 / "exceptions.csv", index=False, float_format="%.2f")
    print(f"exceptions.csv: {len(out)} rows "
          f"({(out.classification == GENUINE).sum()} genuine breaks, {(out.classification == TIMING).sum()} timing, "
          f"{(out.classification == NOT_A_PROBLEM).sum()} not a problem); bridge residual {residual:.2f}; "
          f"lag median {ctx['median_lag']}, max {ctx['max_lag']}")
    for line, amt in rows.groupby("bridge_line").bridge_amount.sum().items():
        if line:
            print(f"  {line}: {amt:,.2f}")

    from build_workbook import write_workbook  # noqa: E402  (sibling module)
    write_workbook(EX1 / "Reconciliation_Workbook.xlsx", out, dep, gw, BRIDGE_LINES, CATEGORIES,
                   (GENUINE, TIMING, NOT_A_PROBLEM), {"median": ctx["median_lag"], "max": ctx["max_lag"]})
    print("Reconciliation_Workbook.xlsx written")


if __name__ == "__main__":
    main()
