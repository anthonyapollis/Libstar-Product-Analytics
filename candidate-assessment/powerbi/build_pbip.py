"""Generate the Power BI Project (.pbip) for the JSB reporting model.

One definition of tables, relationships and measures drives four outputs,
so they cannot drift apart:
  * JSB_Assessment.SemanticModel/model.bim  (tables, Power Query, relationships, DAX)
  * JSB_Assessment.Report/report.json       (two report pages)
  * measures.dax                            (the same DAX, for reading/pasting)
  * expected_values.md                      (what each visual should show, computed
                                             independently from the CSVs with pandas)
It then validates the result. Run: python build_pbip.py
"""
import json
import re
import shutil
import uuid
from itertools import count
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
NAME = "JSB_Assessment"
MODEL_DIR = HERE / f"{NAME}.SemanticModel"
REPORT_DIR = HERE / f"{NAME}.Report"
THEME_SRC = HERE / "theme" / "CY24SU06.json"   # taken from the supplied Demo.pbix

# M type, TOM dataType, TOM formatString
T = {
    "int":  ("Int64.Type",    "int64",    "0"),
    "text": ("type text",     "string",   None),
    "money": ("Currency.Type", "decimal", "#,0.00"),   # fixed decimal, 4dp, matches DECIMAL(18,4)
    "num":  ("type number",   "double",   "#,0.000"),
    "date": ("type date",     "dateTime", "yyyy-mm-dd"),
    "dt":   ("type datetime", "dateTime", "yyyy-mm-dd hh:nn:ss"),
}

TABLES = {
    "dim_player": {
        "player_id": "int", "kyc_status": "text", "current_vip_tier": "text", "status": "text",
        "traffic_source": "text", "affiliate_id": "int", "preferred_currency": "text",
        "registered_at_utc": "dt",
    },
    "dim_player_vip_tier_scd": {
        "player_id": "int", "vip_tier": "text", "valid_from_utc": "dt", "valid_to_utc": "dt",
        "is_current": "int",
    },
    "dim_campaign": {
        "campaign_id": "int", "campaign_name": "text", "campaign_type": "text",
        "rollover_multiple": "num", "min_odds": "num", "valid_from_utc": "dt", "valid_to_utc": "dt",
    },
    "dim_date": {
        "date_day": "date", "year": "int", "month": "int", "day": "int", "day_name": "text",
        "is_weekend": "int",
    },
    "fact_bet": {
        "bet_id": "int", "player_id": "int", "vip_tier_at_bet_time": "text", "product": "text",
        "channel": "text", "placed_date": "date", "stake_real_amount": "money",
        "stake_bonus_amount": "money", "total_stake": "money", "status": "text",
        "payout_amount": "money", "ggr_contribution": "money", "placed_at_utc": "dt",
        "settled_at_utc": "dt",
    },
    "fact_wallet_transaction": {
        "wallet_txn_id": "int", "wallet_id": "int", "player_id": "int", "txn_type": "text",
        "balance_type": "text", "amount": "money", "direction": "text", "signed_amount": "money",
        "balance_before": "money", "balance_after": "money", "related_bet_id": "int",
        "related_deposit_attempt_id": "int", "related_withdrawal_id": "int",
        "related_player_bonus_id": "int", "reversal_of_wallet_txn_id": "int",
        "idempotency_key": "text", "source_system": "text", "status": "text",
        "transaction_date": "date", "created_at_utc": "dt",
    },
    "fact_bonus_transaction": {
        "player_bonus_id": "int", "player_id": "int", "campaign_id": "int", "campaign_name": "text",
        "campaign_type": "text", "granted_amount": "money", "rollover_required": "money",
        "rollover_progress": "money", "status": "text", "realised_bonus_cost": "money",
        "granted_at_utc": "dt", "expires_at_utc": "dt", "resolved_at_utc": "dt",
    },
}

# (many side table, column) -> (one side table, column). Filters flow one -> many only.
# fact_wallet_transaction.related_bet_id / related_player_bonus_id are kept as keys
# for drill-through but NOT modelled as relationships: joining facts to facts would
# give dim_player two filter paths to fact_wallet_transaction (ambiguous).
RELATIONSHIPS = [
    ("fact_bet", "player_id", "dim_player", "player_id"),
    ("fact_wallet_transaction", "player_id", "dim_player", "player_id"),
    ("fact_bonus_transaction", "player_id", "dim_player", "player_id"),
    ("dim_player_vip_tier_scd", "player_id", "dim_player", "player_id"),
    ("fact_bet", "placed_date", "dim_date", "date_day"),
    ("fact_wallet_transaction", "transaction_date", "dim_date", "date_day"),
    ("fact_bonus_transaction", "campaign_id", "dim_campaign", "campaign_id"),
]

# table -> [(measure, DAX, format)]. Definitions match exercise3-schema-design/example_queries.sql.
MEASURES = {
    "fact_bet": [
        ("Turnover", 'CALCULATE ( SUM ( fact_bet[total_stake] ), fact_bet[status] IN { "won", "lost" } )', "#,0.00"),
        ("Payouts", 'CALCULATE ( SUM ( fact_bet[payout_amount] ), fact_bet[status] IN { "won", "lost" } )', "#,0.00"),
        ("GGR", "[Turnover] - [Payouts]", "#,0.00"),
        # Realised bonus cost = bonus money staked on bets that lost (query (a)).
        ("Bonus Cost (realised)", 'CALCULATE ( SUM ( fact_bet[stake_bonus_amount] ), fact_bet[status] = "lost" )', "#,0.00"),
        ("NGR", "[GGR] - [Bonus Cost (realised)]", "#,0.00"),
    ],
    "fact_bonus_transaction": [
        # Campaign cost is recognised when a grant resolves (query (b)).
        ("Campaign Bonus Cost",
         'CALCULATE ( SUM ( fact_bonus_transaction[granted_amount] ), fact_bonus_transaction[status] IN { "completed", "expired", "forfeited" } )',
         "#,0.00"),
        ("Campaign Bonus Cost % of NGR",
         "DIVIDE ( [Campaign Bonus Cost], CALCULATE ( [NGR], REMOVEFILTERS ( dim_campaign ) ) )", "0.00%"),
        ("Bonus Liability Outstanding",
         'CALCULATE ( SUM ( fact_bonus_transaction[granted_amount] ), fact_bonus_transaction[status] = "active" )', "#,0.00"),
    ],
    "fact_wallet_transaction": [
        ("Deposits", 'CALCULATE ( SUM ( fact_wallet_transaction[amount] ), fact_wallet_transaction[txn_type] = "deposit" )', "#,0.00"),
        # Point-in-time balance from the ledger (query (c)): everything posted up to the
        # last date in the current date filter.
        ("Balance as of selected date",
         "VAR AsOf = MAX ( dim_date[date_day] )\nRETURN\n    CALCULATE (\n        SUM ( fact_wallet_transaction[signed_amount] ),\n        REMOVEFILTERS ( dim_date ),\n        fact_wallet_transaction[transaction_date] <= AsOf,\n        fact_wallet_transaction[status] = \"posted\"\n    )",
         "#,0.00"),
    ],
}

_ids = count(1)


def guid():
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"jsb-pbip-{next(_ids)}"))


def m_query(table):
    cols = TABLES[table]
    types = ", ".join(f'{{"{c}", {T[t][0]}}}' for c, t in cols.items())
    return [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        "    Blanks = Table.TransformColumns(Promoted, List.Transform(Table.ColumnNames(Promoted), each {_, (v) => if v = \"\" then null else v})),",
        f'    Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]


def build_model():
    tables = []
    for tname, cols in TABLES.items():
        columns = []
        for c, t in cols.items():
            col = {"name": c, "dataType": T[t][1], "sourceColumn": c, "lineageTag": guid(),
                   "summarizeBy": "none"}
            if T[t][2]:
                col["formatString"] = T[t][2]
            if t == "money":
                col["summarizeBy"] = "sum"
            columns.append(col)
        table = {
            "name": tname,
            "lineageTag": guid(),
            "columns": columns,
            "partitions": [{"name": tname, "mode": "import",
                            "source": {"type": "m", "expression": m_query(tname)}}],
            "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
        }
        if tname in MEASURES:
            table["measures"] = [
                {"name": n, "expression": e.split("\n") if "\n" in e else e,
                 "formatString": f, "lineageTag": guid()}
                for n, e, f in MEASURES[tname]
            ]
        tables.append(table)

    relationships = [
        {"name": guid(), "fromTable": ft, "fromColumn": fc, "toTable": tt, "toColumn": tc}
        for ft, fc, tt, tc in RELATIONSHIPS
    ]
    return {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "relationships": relationships,
            "expressions": [{
                "name": "DataFolder",
                "kind": "m",
                "expression": '"C:\\JSB\\powerbi\\data\\" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
                "lineageTag": guid(),
                "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
            }],
            "annotations": [
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                {"name": "PBI_QueryOrder", "value": json.dumps(["DataFolder", *TABLES])},
            ],
        },
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def field(table, name, kind, alias):
    key = "Measure" if kind == "m" else "Column"
    return {key: {"Expression": {"SourceRef": {"Source": alias}}, "Property": name},
            "Name": f"{table}.{name}"}


def visual(name, vtype, pos, roles=None, objects=None):
    """roles: {projection role: [(table, field, 'm'|'c'), ...]}"""
    x, y, w, h = pos
    sv = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if roles:
        aliases, froms, selects, projections = {}, [], [], {}
        for role, fields in roles.items():
            projections[role] = []
            for table, fname, kind in fields:
                if table not in aliases:
                    aliases[table] = f"t{len(aliases)}"
                    froms.append({"Name": aliases[table], "Entity": table, "Type": 0})
                ref = f"{table}.{fname}"
                if ref not in [s["Name"] for s in selects]:
                    selects.append(field(table, fname, kind, aliases[table]))
                proj = {"queryRef": ref}
                if kind == "c" and role in ("Category", "Values") and vtype != "tableEx":
                    proj["active"] = True
                projections[role].append(proj)
        sv["projections"] = projections
        sv["prototypeQuery"] = {"Version": 2, "From": froms, "Select": selects}
    if objects:
        sv["objects"] = objects
    cfg = {"name": name, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
           "singleVisual": sv}
    return {"x": x, "y": y, "z": 0, "width": w, "height": h, "config": json.dumps(cfg), "filters": "[]"}


def textbox(name, text, pos, size="20pt"):
    return visual(name, "textbox", pos, objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": size}}]}]}}]})


def build_report():
    fb, fbt, fwt = "fact_bet", "fact_bonus_transaction", "fact_wallet_transaction"
    page1 = [
        textbox("title1", "JSB — NGR overview (seed data, September 2026)", (20, 10, 900, 50)),
        visual("card_ggr", "card", (20, 70, 290, 110), {"Values": [(fb, "GGR", "m")]}),
        visual("card_bonus", "card", (330, 70, 290, 110), {"Values": [(fb, "Bonus Cost (realised)", "m")]}),
        visual("card_ngr", "card", (640, 70, 290, 110), {"Values": [(fb, "NGR", "m")]}),
        visual("card_liab", "card", (950, 70, 310, 110), {"Values": [(fbt, "Bonus Liability Outstanding", "m")]}),
        visual("col_ngr_product", "clusteredColumnChart", (20, 200, 700, 500),
               {"Category": [(fb, "product", "c")], "Y": [(fb, "GGR", "m"), (fb, "NGR", "m")]}),
        visual("tbl_campaign", "tableEx", (740, 200, 520, 240),
               {"Values": [("dim_campaign", "campaign_name", "c"), (fbt, "Campaign Bonus Cost", "m"),
                           (fbt, "Campaign Bonus Cost % of NGR", "m")]}),
    ]
    page2 = [
        textbox("title2", "JSB — player balances from the ledger", (20, 10, 900, 50)),
        visual("slicer_date", "slicer", (20, 70, 400, 120), {"Values": [("dim_date", "date_day", "c")]}),
        visual("card_deposits", "card", (440, 70, 290, 120), {"Values": [(fwt, "Deposits", "m")]}),
        visual("tbl_balance", "tableEx", (20, 210, 700, 300),
               {"Values": [("dim_player", "player_id", "c"), (fwt, "balance_type", "c"),
                           (fwt, "Balance as of selected date", "m")]}),
    ]
    sections = []
    for i, (disp, visuals) in enumerate([("NGR overview", page1), ("Player balances", page2)]):
        sections.append({"id": i, "name": f"ReportSection{i + 1}", "displayName": disp, "filters": "[]",
                         "ordinal": i, "visualContainers": visuals, "config": "{}", "displayOption": 1,
                         "width": 1280, "height": 720})
    config = {
        "version": "5.55",
        "themeCollection": {"baseTheme": {"name": "CY24SU06", "version": "5.55", "type": 2}},
        "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
        "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                     "useStylableVisualContainerHeader": True, "queryLimitOption": 6,
                     "exportDataMode": 1, "useDefaultAggregateDisplayName": True},
        "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
    }
    return {
        "config": json.dumps(config),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {"name": "SharedResources", "type": 2, "items": [
            {"type": 202, "path": "BaseThemes/CY24SU06.json", "name": "CY24SU06"}], "disabled": False}}],
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate(model, report):
    tables = {t["name"]: t for t in model["model"]["tables"]}
    cols = {(t, c["name"]) for t, tb in tables.items() for c in tb["columns"]}
    meas = {(t, m["name"]) for t, tb in tables.items() for m in tb.get("measures", [])}
    meas_names = {m for _, m in meas}
    errors = []

    for r in model["model"]["relationships"]:
        for side in ("from", "to"):
            if (r[f"{side}Table"], r[f"{side}Column"]) not in cols:
                errors.append(f"relationship column missing: {r}")

    # At most one filter path between any two tables (filters flow one-side -> many-side).
    edges = {}
    for ft, _, tt, _ in RELATIONSHIPS:
        edges.setdefault(tt, []).append(ft)

    def paths(a, b, seen):
        if a == b:
            return 1
        return sum(paths(n, b, seen | {n}) for n in edges.get(a, []) if n not in seen)

    for a in tables:
        for b in tables:
            if a != b and paths(a, b, {a}) > 1:
                errors.append(f"ambiguous filter paths {a} -> {b}")

    for t, tb in tables.items():
        for m in tb.get("measures", []):
            expr = m["expression"] if isinstance(m["expression"], str) else "\n".join(m["expression"])
            for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", expr):
                if ref not in meas_names:
                    errors.append(f"{t}[{m['name']}] references unknown measure [{ref}]")
            for tbl, col in re.findall(r"\b(\w+)\[([^\]]+)\]", expr):
                if (tbl, col) not in cols:
                    errors.append(f"{t}[{m['name']}] references unknown column {tbl}[{col}]")
            if expr.count("(") != expr.count(")"):
                errors.append(f"{t}[{m['name']}] unbalanced parentheses")

    for s in report["sections"]:
        for vc in s["visualContainers"]:
            cfg = json.loads(vc["config"])
            sv = cfg["singleVisual"]
            if "prototypeQuery" not in sv:
                continue
            alias = {f["Name"]: f["Entity"] for f in sv["prototypeQuery"]["From"]}
            names = set()
            for sel in sv["prototypeQuery"]["Select"]:
                kind = "Measure" if "Measure" in sel else "Column"
                ent = alias[sel[kind]["Expression"]["SourceRef"]["Source"]]
                prop = sel[kind]["Property"]
                if (ent, prop) not in (meas if kind == "Measure" else cols):
                    errors.append(f"visual {cfg['name']}: {kind} {ent}.{prop} not in model")
                names.add(sel["Name"])
            for role, refs in sv["projections"].items():
                for p in refs:
                    if p["queryRef"] not in names:
                        errors.append(f"visual {cfg['name']}: projection {p['queryRef']} not selected")
    return errors


# ---------------------------------------------------------------------------
# Expected values, computed independently of DAX with pandas
# ---------------------------------------------------------------------------
def expected_values():
    bet = pd.read_csv(DATA / "fact_bet.csv")
    bon = pd.read_csv(DATA / "fact_bonus_transaction.csv")
    wal = pd.read_csv(DATA / "fact_wallet_transaction.csv", parse_dates=["transaction_date"])
    dates = pd.read_csv(DATA / "dim_date.csv", parse_dates=["date_day"])
    settled = bet[bet.status.isin(["won", "lost"])]

    def ngr(df):
        ggr = df.total_stake.sum() - df.payout_amount.sum()
        return ggr, ggr - df[df.status == "lost"].stake_bonus_amount.sum()

    ggr_all, ngr_all = ngr(settled)
    bonus_realised = settled[settled.status == "lost"].stake_bonus_amount.sum()
    camp = bon[bon.status.isin(["completed", "expired", "forfeited"])].granted_amount.sum()
    liab = bon[bon.status == "active"].granted_amount.sum()
    lines = [
        "# Expected values in the Power BI report",
        "",
        "Computed with pandas straight from `data/*.csv`, independently of the DAX. Open the",
        "report, refresh, and each visual should show exactly these numbers. They also match",
        "`exercise3-schema-design/example_queries.sql` and the dbt marts.",
        "",
        "## Page 1: NGR overview",
        "",
        "| Visual | Expected |",
        "|---|---|",
        f"| Card: GGR | {ggr_all:,.2f} |",
        f"| Card: Bonus Cost (realised) | {bonus_realised:,.2f} |",
        f"| Card: NGR | {ngr_all:,.2f} |",
        f"| Card: Bonus Liability Outstanding | {liab:,.2f} |",
    ]
    for prod, df in settled.groupby("product"):
        g, n = ngr(df)
        lines.append(f"| Column chart, {prod}: GGR / NGR | {g:,.2f} / {n:,.2f} |")
    lines.append(f"| Table, Registration Bonus: Campaign Bonus Cost / % of NGR | {camp:,.2f} / {camp / ngr_all:.2%} |")
    lines += ["", "## Page 2: Player balances", "",
              "| Date slicer upper bound | Player | Balance type | Expected balance |", "|---|---|---|---|"]
    for as_of in [pd.Timestamp("2026-09-06"), dates.date_day.max()]:
        w = wal[(wal.transaction_date <= as_of) & (wal.status == "posted")]
        for (pid, bt), v in w.groupby(["player_id", "balance_type"]).signed_amount.sum().items():
            lines.append(f"| {as_of.date()} | {pid} | {bt} | {v:,.2f} |")
    dep = wal[wal.txn_type == "deposit"].amount.sum()
    lines += ["", f"Card: Deposits (full date range) = {dep:,.2f}", ""]
    return "\n".join(lines)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def platform(kind, name):
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": kind, "displayName": name},
        "config": {"version": "2.0", "logicalId": guid()},
    }


def main():
    model, report = build_model(), build_report()
    errors = validate(model, report)
    if errors:
        raise SystemExit("VALIDATION FAILED:\n  " + "\n  ".join(errors))

    for d in (MODEL_DIR, REPORT_DIR):
        shutil.rmtree(d, ignore_errors=True)
    write_json(HERE / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write_json(MODEL_DIR / "definition.pbism", {"version": "1.0", "settings": {}})
    write_json(MODEL_DIR / ".platform", platform("SemanticModel", NAME))
    write_json(MODEL_DIR / "model.bim", model)
    write_json(REPORT_DIR / "definition.pbir", {
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}, "byConnection": None},
    })
    write_json(REPORT_DIR / ".platform", platform("Report", NAME))
    write_json(REPORT_DIR / "report.json", report)
    theme_dst = REPORT_DIR / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU06.json"
    theme_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(THEME_SRC, theme_dst)

    dax = ["-- Generated by build_pbip.py from the same definitions as model.bim.", ""]
    for t, ms in MEASURES.items():
        dax.append(f"-- ===== table: {t} =====")
        for n, e, f in ms:
            dax += [f"{n} =", *("    " + line for line in e.split("\n")), f"    -- format: {f}", ""]
    (HERE / "measures.dax").write_text("\n".join(dax), encoding="utf-8")
    (HERE / "expected_values.md").write_text(expected_values(), encoding="utf-8")

    n_meas = sum(len(v) for v in MEASURES.values())
    n_vis = sum(len(s["visualContainers"]) for s in report["sections"])
    print(f"OK: {len(TABLES)} tables, {len(RELATIONSHIPS)} relationships (no ambiguous paths), "
          f"{n_meas} measures, {len(report['sections'])} pages, {n_vis} visuals -- all references resolve")


if __name__ == "__main__":
    main()
