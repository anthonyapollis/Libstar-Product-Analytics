"""Generate the Power BI Project (.pbip) for the JSB assessment.

One definition of tables, relationships, measures and pages drives every output,
so they cannot drift apart:
  * JSB_Assessment.SemanticModel/model.bim  (tables, Power Query, relationships, DAX)
  * JSB_Assessment.Report/report.json       (four report pages)
  * measures.dax                            (the same DAX, readable)
  * expected_values.md                      (what each visual should show, computed
                                             independently from the CSVs with pandas)
It validates the result before writing anything.

  python build_pbip.py            data embedded in the model: opens and refreshes anywhere
  python build_pbip.py --folder   reads data/*.csv from a DataFolder parameter instead
                                  (use for full-volume extracts too big to embed)
"""
import base64
import json
import re
import shutil
import sys
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
FOLDER_MODE = "--folder" in sys.argv

# M type, TOM dataType, TOM formatString
T = {
    "int":   ("Int64.Type",    "int64",    "0"),
    "text":  ("type text",     "string",   None),
    "money": ("Currency.Type", "decimal",  "#,0.00"),   # fixed decimal, 4dp, matches DECIMAL(18,4)
    "num":   ("type number",   "double",   "#,0.000"),
    "date":  ("type date",     "dateTime", "yyyy-mm-dd"),
    "dt":    ("type datetime", "dateTime", "yyyy-mm-dd hh:nn:ss"),
}

TABLES = {
    # ---- Exercise 3: reporting star schema ----
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
        "stake_bonus_amount": "money", "total_stake": "money", "player_bonus_id": "int",
        "campaign_id": "int", "status": "text", "payout_amount": "money", "ggr_contribution": "money",
        "bonus_cost": "money", "ngr_contribution": "money", "placed_at_utc": "dt",
        "settled_at_utc": "dt",
    },
    "fact_wallet_transaction": {
        "wallet_txn_id": "int", "wallet_id": "int", "player_id": "int", "txn_type": "text",
        "balance_type": "text", "amount": "money", "direction": "text", "signed_amount": "money",
        "balance_before": "money", "balance_after": "money", "related_bet_id": "int",
        "related_deposit_attempt_id": "int", "related_withdrawal_id": "int",
        "related_player_bonus_id": "int", "reversal_of_wallet_txn_id": "int",
        "idempotency_key": "text", "source_system": "text",
        "transaction_date": "date", "created_at_utc": "dt",
    },
    "fact_bonus_transaction": {
        "player_bonus_id": "int", "player_id": "int", "campaign_id": "int", "campaign_name": "text",
        "campaign_type": "text", "granted_amount": "money", "rollover_required": "money",
        "rollover_progress": "money", "status": "text", "bonus_wagered": "money",
        "bonus_cost": "money", "bonus_outstanding": "money",
        "granted_at_utc": "dt", "expires_at_utc": "dt", "resolved_at_utc": "dt",
    },
    # ---- Exercise 1: reconciliation (dbt marts) ----
    "fct_recon_exceptions": {
        "deposit_id": "text", "player_id": "text", "created_at": "dt", "dep_amount": "money",
        "gateway_ref": "text", "settlement_row_id": "int", "gateway_txn_id": "text",
        "merchant_ref": "text", "settled_at": "dt", "gross_amount": "money", "fee": "money",
        "net_amount": "money", "gw_status": "text", "expected_fee": "money", "category": "text",
        "financial_impact": "money", "category_type": "text", "recon_key": "text",
    },
    "mart_recon_bridge": {
        "step_order": "int", "step": "text", "amount": "money", "gateway_settled_total": "money",
    },
    # ---- Exercise 2: ingestion (dbt staging) ----
    "ingest_runs": {
        "run_id": "int", "source_system": "text", "started_at": "dt", "finished_at": "dt",
        "status": "text", "pages_fetched": "int", "rows_upserted": "int", "rows_new": "int",
        "rows_changed": "int", "rows_unchanged": "int", "rows_rejected": "int",
        "rate_limit_hits": "int", "server_error_hits": "int", "duration_seconds": "int",
    },
    "transactions": {
        "id": "text", "player_id": "text", "type": "text", "amount": "money", "currency": "text",
        "status": "text", "updated_at": "dt", "ingested_at": "dt", "source_system": "text",
    },
}
SORT_BY = {("mart_recon_bridge", "step"): "step_order"}   # waterfall steps in bridge order

# Short labels for chart axes: the dbt category text is a full sentence and gets truncated.
CATEGORY_LABELS = [
    ("OK: matched, amount and fee correct", "Matched"),
    ("BREAK: duplicate internal SUCCESS deposit for one settlement (double-credit risk)", "Duplicate internal deposit"),
    ("BREAK: deposit SUCCESS, no gateway settlement found", "No settlement found"),
    ("BREAK: settled fee differs from contracted fee", "Fee above contract"),
    ("BREAK: settled gross amount differs from internal amount", "Gross amount differs"),
    ("BREAK: duplicate gateway settlement for one reference (double-credit risk)", "Duplicate gateway row"),
    ("BREAK: unrecognised settlement (no internal record)", "Unrecognised settlement"),
    ("BREAK: net amount is not gross minus fee", "Net not gross minus fee"),
    ("BREAK: payment confirmed, wallet not credited", "Settled, marked FAILED"),
    ("NOT A PROBLEM: rounding difference <= 1 cent", "Rounding (1 cent or less)"),
    ("REVERSAL: gateway reversed/charged back after settlement", "Reversal / chargeback"),
    ("TIMING: settlement expected in next period (created near cut-off)", "Settles next period"),
    ("TIMING: prior-period deposit settled at start of period", "Prior-period deposit"),
]
# table -> [(column, DAX)] calculated in the model, not read from the CSV
CALCULATED = {
    "fct_recon_exceptions": [(
        "category_label",
        "SWITCH ( fct_recon_exceptions[category],\n"
        + "".join(f'    "{full}", "{short}",\n' for full, short in CATEGORY_LABELS)
        + "    fct_recon_exceptions[category] )",
    )],
}

# (many side table, column) -> (one side table, column). Filters flow one -> many only.
# fact_wallet_transaction.related_bet_id / related_player_bonus_id are kept as keys
# for drill-through but NOT modelled as relationships: joining facts to facts would
# give dim_player two filter paths to fact_wallet_transaction (ambiguous).
# The Exercise 1 and 2 tables stand alone: they share no keys with the player model.
RELATIONSHIPS = [
    ("fact_bet", "player_id", "dim_player", "player_id"),
    ("fact_wallet_transaction", "player_id", "dim_player", "player_id"),
    ("fact_bonus_transaction", "player_id", "dim_player", "player_id"),
    ("dim_player_vip_tier_scd", "player_id", "dim_player", "player_id"),
    ("fact_bet", "placed_date", "dim_date", "date_day"),
    ("fact_wallet_transaction", "transaction_date", "dim_date", "date_day"),
    ("fact_bonus_transaction", "campaign_id", "dim_campaign", "campaign_id"),
]

# Tile colours for status KPIs: a text measure returning a hex colour, bound to the tile
# background, so the colour follows the number (green = fine, amber = look, red = act).
TILE_GREEN, TILE_AMBER, TILE_RED = '"#1E8C5A"', '"#D9901A"', '"#C8413A"'


def tile_rule(condition, when_true, when_false):
    return f"IF ( {condition}, {when_true}, {when_false} )"


ACT_NOW = ('"BREAK: payment confirmed, wallet not credited", '
           '"BREAK: unrecognised settlement (no internal record)"')

# table -> [(measure, DAX, format)]
MEASURES = {
    "fact_bet": [
        ("GGR Tile Colour", tile_rule("[GGR] < 0", TILE_RED, TILE_GREEN), None),
        ("NGR Tile Colour", tile_rule("[NGR] < 0", TILE_RED, TILE_GREEN), None),
        ("Turnover", 'CALCULATE ( SUM ( fact_bet[total_stake] ), fact_bet[status] IN { "won", "lost" } )', "#,0.00"),
        ("Payouts", 'CALCULATE ( SUM ( fact_bet[payout_amount] ), fact_bet[status] IN { "won", "lost" } )', "#,0.00"),
        ("GGR", "[Turnover] - [Payouts]", "#,0.00"),
        # Realised bonus cost = bonus money staked on bets that lost (example query (a)).
        ("Bonus Cost (realised)", "SUM ( fact_bet[bonus_cost] )", "#,0.00"),
        ("NGR", "[GGR] - [Bonus Cost (realised)]", "#,0.00"),
    ],
    "fact_bonus_transaction": [
        # Campaign cost is recognised when a grant resolves (example query (b)).
        ("Campaign Bonus Cost",
         "SUM ( fact_bonus_transaction[bonus_cost] )",
         "#,0.00"),
        ("Campaign Bonus Cost % of NGR",
         "DIVIDE ( [Campaign Bonus Cost], CALCULATE ( [NGR], REMOVEFILTERS ( dim_campaign ) ) )", "0.00%"),
        ("Bonus Liability Outstanding",
         "SUM ( fact_bonus_transaction[bonus_outstanding] )", "#,0.00"),
    ],
    "fact_wallet_transaction": [
        ("Deposits", 'CALCULATE ( SUM ( fact_wallet_transaction[amount] ), fact_wallet_transaction[txn_type] = "deposit" )', "#,0.00"),
        # Point-in-time balance from the ledger (example query (c)).
        ("Balance as of selected date",
         "VAR AsOf = MAX ( dim_date[date_day] )\nRETURN\n    CALCULATE (\n        SUM ( fact_wallet_transaction[signed_amount] ),\n        REMOVEFILTERS ( dim_date ),\n        fact_wallet_transaction[transaction_date] <= AsOf\n    )",
         "#,0.00"),
    ],
    "fct_recon_exceptions": [
        ("Exceptions Tile Colour", tile_rule("[Exceptions] > 0", TILE_AMBER, TILE_GREEN), None),
        ("Act Now Tile Colour", tile_rule("[Act Now Value] > 0", TILE_RED, TILE_GREEN), None),
        ("Settlements Matched Exactly",
         'CALCULATE ( COUNTROWS ( fct_recon_exceptions ), fct_recon_exceptions[category_type] = "OK" )', "#,0"),
        ("Exceptions",
         'CALCULATE ( COUNTROWS ( fct_recon_exceptions ), fct_recon_exceptions[category_type] <> "OK" )', "#,0"),
        ("Exception Impact",
         'CALCULATE ( SUM ( fct_recon_exceptions[financial_impact] ), fct_recon_exceptions[category_type] <> "OK" )', "#,0.00"),
        ("Act Now Value",
         f"CALCULATE ( SUM ( fct_recon_exceptions[financial_impact] ), fct_recon_exceptions[category] IN {{ {ACT_NOW} }} )",
         "#,0.00"),
    ],
    "mart_recon_bridge": [
        ("Residual Tile Colour", tile_rule("ABS ( [Bridge Residual] ) < 0.005", TILE_GREEN, TILE_RED), None),
        ("Bridge Amount", "SUM ( mart_recon_bridge[amount] )", "#,0.00"),
        # Must be 0.00: every rand between the two totals is explained by a bridge step.
        ("Bridge Residual", "SUM ( mart_recon_bridge[amount] ) - MAX ( mart_recon_bridge[gateway_settled_total] )", "#,0.00"),
    ],
    "ingest_runs": [
        ("Rejected Tile Colour", tile_rule("[Rows Rejected] > 0", TILE_AMBER, TILE_GREEN), None),
        ("Ingestion Runs", "COUNTROWS ( ingest_runs )", "#,0"),
        ("Rows Rejected", "SUM ( ingest_runs[rows_rejected] )", "#,0"),
        ("API Retries", "SUM ( ingest_runs[rate_limit_hits] ) + SUM ( ingest_runs[server_error_hits] )", "#,0"),
        ("Rows New", "SUM ( ingest_runs[rows_new] )", "#,0"),
        ("Rows Changed", "SUM ( ingest_runs[rows_changed] )", "#,0"),
    ],
    "transactions": [
        ("Transactions Loaded", "DISTINCTCOUNT ( transactions[id] )", "#,0"),
    ],
}

_ids = count(1)


def guid():
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"jsb-pbip-{next(_ids)}"))


def m_query(table):
    cols = TABLES[table]
    types = ", ".join(f'{{"{c}", {T[t][0]}}}' for c, t in cols.items())
    if FOLDER_MODE:
        source = f'File.Contents(DataFolder & "{table}.csv")'
    else:
        b64 = base64.b64encode((DATA / f"{table}.csv").read_bytes()).decode()
        source = f'Binary.FromText("{b64}", BinaryEncoding.Base64)'
    return [
        "let",
        f"    Source = Csv.Document({source}, [Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
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
                   "summarizeBy": "sum" if t == "money" else "none"}
            if T[t][2]:
                col["formatString"] = T[t][2]
            if (tname, c) in SORT_BY:
                col["sortByColumn"] = SORT_BY[(tname, c)]
            columns.append(col)
        for c, expr in CALCULATED.get(tname, []):
            columns.append({"type": "calculated", "name": c, "dataType": "string",
                            "isDataTypeInferred": True, "expression": expr.split("\n"),
                            "lineageTag": guid(), "summarizeBy": "none"})
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
                 **({"formatString": f} if f else {}), "lineageTag": guid()}
                for n, e, f in MEASURES[tname]
            ]
        tables.append(table)

    model = {
        "culture": "en-US",
        "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "sourceQueryCulture": "en-US",
        "tables": tables,
        "relationships": [
            {"name": guid(), "fromTable": ft, "fromColumn": fc, "toTable": tt, "toColumn": tc}
            for ft, fc, tt, tc in RELATIONSHIPS
        ],
        "annotations": [
            {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            {"name": "PBI_QueryOrder",
             "value": json.dumps((["DataFolder"] if FOLDER_MODE else []) + list(TABLES))},
        ],
    }
    if FOLDER_MODE:
        model["expressions"] = [{
            "name": "DataFolder", "kind": "m",
            "expression": '"C:\\JSB\\powerbi\\data\\" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
            "lineageTag": guid(),
            "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
        }]
    return {"compatibilityLevel": 1567, "model": model}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def field(table, name, kind, alias):
    key = "Measure" if kind == "m" else "Column"
    return {key: {"Expression": {"SourceRef": {"Source": alias}}, "Property": name},
            "Name": f"{table}.{name}"}


# ---- styling -------------------------------------------------------------
NAVY, PAGE_BG, BORDER, WHITE = "#16325C", "#EEF2F7", "#D6DEE9", "#FFFFFF"
GREEN, RED, AMBER, PURPLE, GREY = "#1E8C5A", "#C8413A", "#D9901A", "#6E4FC2", "#8A94A6"
TEAL = "#1F7A8C"
LIGHT_BLUE = "#8DB3E2"


def color(hex_):
    return {"solid": {"color": lit(f"'{hex_}'")}}


def value_selector(table, column, value):
    """dataPoint selector for one category/series value."""
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0,
        "Left": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
        "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}


def fills(table, column, mapping):
    return [{"properties": {"fill": color(c)}, "selector": value_selector(table, column, v)}
            for v, c in mapping.items()]


def container(bg=WHITE, border=BORDER, title=None, radius="8D"):
    vc = {"background": [{"properties": {"show": lit("true"), "color": color(bg), "transparency": lit("0D")}}],
          "border": [{"properties": {"show": lit("true"), "color": color(border), "radius": lit(radius)}}]}
    if title:
        vc["title"] = [{"properties": {"show": lit("true"), "text": lit(f"'{title}'"),
                                       "fontColor": color(NAVY), "fontSize": lit("12D"), "bold": lit("true")}}]
    return vc


TABLE_STYLE = {
    "columnHeaders": [{"properties": {"fontColor": color(WHITE), "backColor": color(NAVY)}}],
    "values": [{"properties": {"backColorPrimary": color(WHITE), "backColorSecondary": color("#F4F7FB")}}],
    "total": [{"properties": {"backColor": color("#E3EAF4"), "fontColor": color(NAVY)}}],
    "grid": [{"properties": {"gridHorizontal": lit("true"), "gridHorizontalColor": color(BORDER),
                             "rowPadding": lit("4D")}}],
}


def visual(name, vtype, pos, roles=None, title=None, labels=False, order=None, objects=None, vc=None):
    """roles: {projection role: [(table, field, 'm'|'c'), ...]};
    order: (table, field, 'm'|'c', ascending)."""
    x, y, w, h = pos
    sv = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if roles:
        aliases, froms, selects, projections = {}, [], [], {}

        def alias_for(table):
            if table not in aliases:
                aliases[table] = f"t{len(aliases)}"
                froms.append({"Name": aliases[table], "Entity": table, "Type": 0})
            return aliases[table]

        for role, fields in roles.items():
            projections[role] = []
            for table, fname, kind in fields:
                ref = f"{table}.{fname}"
                if ref not in [s["Name"] for s in selects]:
                    selects.append(field(table, fname, kind, alias_for(table)))
                proj = {"queryRef": ref}
                if kind == "c" and role == "Category":
                    proj["active"] = True
                projections[role].append(proj)
        sv["projections"] = projections
        sv["prototypeQuery"] = {"Version": 2, "From": froms, "Select": selects}
        if order:
            table, fname, kind, asc = order
            key = "Measure" if kind == "m" else "Column"
            sv["prototypeQuery"]["OrderBy"] = [{
                "Direction": 1 if asc else 2,
                "Expression": {key: {"Expression": {"SourceRef": {"Source": alias_for(table)}},
                                     "Property": fname}}}]
    objs = dict(objects or {})
    if vtype == "tableEx":
        objs = {**TABLE_STYLE, **objs}
    if labels:
        objs.setdefault("labels", [{"properties": {"show": lit("true"), "color": color("#344054")}}])
    if objs:
        sv["objects"] = objs
    sv["vcObjects"] = vc if vc is not None else container(title=title)
    cfg = {"name": name,
           "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
           "singleVisual": sv}
    return {"x": x, "y": y, "z": 0, "width": w, "height": h, "config": json.dumps(cfg), "filters": "[]"}


def banner(name, text, subtitle):
    """Full-width navy title bar."""
    runs = [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": "20pt", "color": WHITE}},
            {"value": "    " + subtitle, "textStyle": {"fontSize": "11pt", "color": "#C9D6EA"}}]
    return visual(name, "textbox", (0, 0, 1280, 58), objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": runs}]}}]}, vc=container(bg=NAVY, border=NAVY, radius="0D"))


def measure_color(table, measure):
    """Colour taken from a measure's value (conditional formatting by field value)."""
    return {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": table}},
                                                     "Property": measure}}}}}


def card(name, table, measure, x, y=74, w=295, h=110, bg=NAVY, rule=None):
    """KPI tile: coloured background, white value, no unit abbreviation (3,150.00 not 3.15K).
    bg: fixed colour for informational tiles; rule: (table, colour measure) for status tiles."""
    vc = container(bg=bg, border=bg, radius="10D")
    if rule:
        for prop in ("background", "border"):
            vc[prop][0]["properties"]["color"] = measure_color(*rule)
    return visual(name, "card", (x, y, w, h), {"Values": [(table, measure, "m")]},
                  objects={"labels": [{"properties": {"color": color(WHITE), "fontSize": lit("26D"),
                                                      "labelDisplayUnits": lit("1D")}}],
                           "categoryLabels": [{"properties": {"color": color("#EEF3F9"), "fontSize": lit("11D")}}]},
                  vc=vc)


PAGE_CONFIG = {"objects": {
    "background": [{"properties": {"color": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{PAGE_BG}'"}}}}},
                                   "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}],
    "outspace": [{"properties": {"color": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{PAGE_BG}'"}}}}},
                                 "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}],
}}


def build_report():
    fb, fbt, fwt = "fact_bet", "fact_bonus_transaction", "fact_wallet_transaction"
    fre, brg, runs, txn = "fct_recon_exceptions", "mart_recon_bridge", "ingest_runs", "transactions"
    X = (20, 335, 650, 965)          # four KPI tiles across a 1280-wide page
    type_colors = {"BREAK": RED, "TIMING": AMBER, "REVERSAL": PURPLE, "NOT A PROBLEM": GREY}
    status_colors = {"completed": GREEN, "failed": RED, "pending": AMBER, "reversed": PURPLE}
    pages = [
        ("NGR overview", [
            banner("title1", "NGR overview", "Exercise 3 seed data, September 2026 · NAD"),
            card("card_ggr", fb, "GGR", X[0], rule=(fb, "GGR Tile Colour")),
            card("card_bonus", fb, "Bonus Cost (realised)", X[1], bg=AMBER),
            card("card_ngr", fb, "NGR", X[2], rule=(fb, "NGR Tile Colour")),
            card("card_liab", fbt, "Bonus Liability Outstanding", X[3], bg=PURPLE),
            visual("col_ngr_product", "clusteredColumnChart", (20, 200, 700, 500),
                   {"Category": [(fb, "product", "c")], "Y": [(fb, "GGR", "m"), (fb, "NGR", "m")]},
                   title="GGR and NGR by product (NAD)", labels=True,
                   objects={"dataPoint": [
                       {"properties": {"fill": color(LIGHT_BLUE)}, "selector": {"metadata": f"{fb}.GGR"}},
                       {"properties": {"fill": color(NAVY)}, "selector": {"metadata": f"{fb}.NGR"}}],
                       "legend": [{"properties": {"show": lit("true"), "position": lit("'Top'")}}]}),
            visual("tbl_campaign", "tableEx", (740, 200, 520, 240),
                   {"Values": [("dim_campaign", "campaign_name", "c"), (fbt, "Campaign Bonus Cost", "m"),
                               (fbt, "Campaign Bonus Cost % of NGR", "m")]},
                   title="Bonus cost as % of NGR, by campaign"),
        ]),
        ("Player balances", [
            banner("title2", "Player balances", "Rebuilt from the append-only wallet ledger · NAD"),
            visual("slicer_date", "slicer", (20, 74, 610, 120), {"Values": [("dim_date", "date_day", "c")]},
                   title="Balance as of (drag the end date)"),
            card("card_deposits", fwt, "Deposits", X[2], h=120, bg=GREEN),
            visual("tbl_balance", "tableEx", (20, 210, 700, 300),
                   {"Values": [("dim_player", "player_id", "c"), (fwt, "balance_type", "c"),
                               (fwt, "Balance as of selected date", "m")]},
                   title="Balance per player, reconstructed from wallet transactions"),
        ]),
        ("Reconciliation", [
            banner("title3", "Gateway reconciliation", "1–7 September 2026 · 306 settlements · NAD"),
            card("card_matched", fre, "Settlements Matched Exactly", X[0], bg=GREEN),
            card("card_exceptions", fre, "Exceptions", X[1], rule=(fre, "Exceptions Tile Colour")),
            card("card_actnow", fre, "Act Now Value", X[2], rule=(fre, "Act Now Tile Colour")),
            card("card_residual", brg, "Bridge Residual", X[3], rule=(brg, "Residual Tile Colour")),
            visual("wf_bridge", "waterfallChart", (20, 200, 760, 500),
                   {"Category": [(brg, "step", "c")], "Y": [(brg, "Bridge Amount", "m")]},
                   title="Bridge: internal total to gateway total (axis starts at 205,000)",
                   order=(brg, "step", "c", True),
                   objects={"labels": [{"properties": {"show": lit("true"), "labelDisplayUnits": lit("1D"),
                                                       "labelPrecision": lit("0L"), "color": color("#344054")}}],
                            "valueAxis": [{"properties": {"start": lit("205000D")}}],
                            "sentimentColors": [{"properties": {"increaseFill": color(GREEN),
                                                                "decreaseFill": color(RED),
                                                                "totalFill": color(NAVY)}}]}),
            visual("bar_categories", "barChart", (800, 200, 460, 300),
                   {"Category": [(fre, "category_label", "c")], "Series": [(fre, "category_type", "c")],
                    "Y": [(fre, "Exceptions", "m")]},
                   title="Exceptions by category", labels=True, order=(fre, "Exceptions", "m", False),
                   objects={"dataPoint": fills(fre, "category_type", type_colors),
                            "legend": [{"properties": {"show": lit("true"), "position": lit("'Top'")}}]}),
            visual("tbl_exceptions", "tableEx", (800, 510, 460, 190),
                   {"Values": [(fre, "category_label", "c"), (fre, "deposit_id", "c"),
                               (fre, "gateway_txn_id", "c"), (fre, "Exception Impact", "m")]},
                   title="Exception detail (matched rows hidden)"),
        ]),
        ("Ingestion monitoring", [
            banner("title4", "API ingestion monitoring", "Exercise 2 · incremental, restartable load · 4 runs"),
            card("card_loaded", txn, "Transactions Loaded", X[0], bg=GREEN),
            card("card_runs", runs, "Ingestion Runs", X[1]),
            card("card_rejected", runs, "Rows Rejected", X[2], rule=(runs, "Rejected Tile Colour")),
            card("card_429", runs, "API Retries", X[3], bg=TEAL),
            visual("tbl_runs", "tableEx", (20, 200, 760, 220),
                   {"Values": [(runs, "run_id", "c"), (runs, "status", "c"), (runs, "started_at", "c"),
                               (runs, "pages_fetched", "c"), (runs, "rows_new", "c"),
                               (runs, "rows_changed", "c"), (runs, "rows_unchanged", "c"),
                               (runs, "rows_rejected", "c"), (runs, "rate_limit_hits", "c"),
                               (runs, "server_error_hits", "c")]},
                   title="Run history: run 1 was killed mid-page (ABANDONED); run 4 loaded only the new and changed records"),
            visual("col_status", "clusteredColumnChart", (800, 200, 460, 500),
                   {"Category": [(txn, "status", "c")], "Y": [(txn, "Transactions Loaded", "m")]},
                   title="Transactions loaded, by status", labels=True,
                   order=(txn, "Transactions Loaded", "m", False),
                   objects={"dataPoint": fills(txn, "status", status_colors)}),
        ]),
    ]
    sections = [{"id": i, "name": f"ReportSection{i + 1}", "displayName": disp, "filters": "[]",
                 "ordinal": i, "visualContainers": visuals, "config": json.dumps(PAGE_CONFIG), "displayOption": 1,
                 "width": 1280, "height": 720}
                for i, (disp, visuals) in enumerate(pages)]
    config = {
        "version": "5.55",
        "themeCollection": {"baseTheme": {"name": "CY24SU06", "version": "5.55", "type": 2}},
        "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
        "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                     "useStylableVisualContainerHeader": True, "queryLimitOption": 6,
                     "exportDataMode": 1, "useDefaultAggregateDisplayName": True},
        "objects": {"section": [{"properties": {"verticalAlignment": lit("'Top'")}}]},
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

    for t, c in SORT_BY.items():
        if t not in cols or (t[0], c) not in cols:
            errors.append(f"sortByColumn {t} -> {c} missing")
    for tname in tables:
        header = pd.read_csv(DATA / f"{tname}.csv", nrows=0).columns.tolist()
        if header != list(TABLES[tname]):
            errors.append(f"{tname}.csv columns {header} != model columns {list(TABLES[tname])}")

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

    def entity_measures(node):
        if isinstance(node, dict):
            m = node.get("Measure")
            if isinstance(m, dict) and "Entity" in m.get("Expression", {}).get("SourceRef", {}):
                yield m["Expression"]["SourceRef"]["Entity"], m["Property"]
            for v in node.values():
                yield from entity_measures(v)
        elif isinstance(node, list):
            for v in node:
                yield from entity_measures(v)

    for s in report["sections"]:
        for vc in s["visualContainers"]:
            cfg = json.loads(vc["config"])
            for ref in entity_measures(cfg):
                if ref not in meas:
                    errors.append(f"visual {cfg['name']}: formatting measure {ref} not in model")
            sv = cfg["singleVisual"]
            if "prototypeQuery" not in sv:
                continue
            q = sv["prototypeQuery"]
            alias = {f["Name"]: f["Entity"] for f in q["From"]}
            names = set()
            items = [(sel, sel) for sel in q["Select"]] + [(o["Expression"], None) for o in q.get("OrderBy", [])]
            for expr, sel in items:
                kind = "Measure" if "Measure" in expr else "Column"
                ent = alias[expr[kind]["Expression"]["SourceRef"]["Source"]]
                prop = expr[kind]["Property"]
                if (ent, prop) not in (meas if kind == "Measure" else cols):
                    errors.append(f"visual {cfg['name']}: {kind} {ent}.{prop} not in model")
                if sel:
                    names.add(sel["Name"])
            for refs in sv["projections"].values():
                for p in refs:
                    if p["queryRef"] not in names:
                        errors.append(f"visual {cfg['name']}: projection {p['queryRef']} not selected")
    return errors


# ---------------------------------------------------------------------------
# Expected values, computed independently of DAX with pandas
# ---------------------------------------------------------------------------
def expected_values():
    rd = lambda n, **kw: pd.read_csv(DATA / f"{n}.csv", **kw)
    bet, bon = rd("fact_bet"), rd("fact_bonus_transaction")
    wal = rd("fact_wallet_transaction", parse_dates=["transaction_date"])
    dates = rd("dim_date", parse_dates=["date_day"])
    rec, brg, runs, txn = rd("fct_recon_exceptions"), rd("mart_recon_bridge"), rd("ingest_runs"), rd("transactions")
    settled = bet[bet.status.isin(["won", "lost"])]

    def ngr(df):
        ggr = df.total_stake.sum() - df.payout_amount.sum()
        return ggr, ggr - df.stake_bonus_amount.sum()

    ggr_all, ngr_all = ngr(settled)
    camp = settled[settled.player_bonus_id.notna()].stake_bonus_amount.sum()   # one campaign in the data
    active = bon[bon.status == "active"]   # liability: active grants' bonus not yet wagered (any bet status)
    liability = active.granted_amount.sum() - bet[bet.player_bonus_id.isin(active.player_bonus_id)].stake_bonus_amount.sum()
    exc = rec[rec.category_type != "OK"]
    act_now = rec[rec.category.isin([
        "BREAK: payment confirmed, wallet not credited",
        "BREAK: unrecognised settlement (no internal record)"])].financial_impact.sum()
    L = [
        "# Expected values in the Power BI report",
        "",
        "Computed with pandas straight from `data/*.csv`, independently of the DAX. After a",
        "refresh, each visual should show exactly these numbers. They also match",
        "`exercise3-schema-design/example_queries.sql`, `exercise1-reconciliation/summary.md`",
        "and the dbt marts.",
        "",
        "## Page 1: NGR overview",
        "",
        "| Visual | Expected |", "|---|---|",
        f"| Card: GGR | {ggr_all:,.2f} |",
        f"| Card: Bonus Cost (realised) | {settled.stake_bonus_amount.sum():,.2f} |",
        f"| Card: NGR | {ngr_all:,.2f} |",
        f"| Card: Bonus Liability Outstanding | {liability:,.2f} |",
    ]
    for prod, df in settled.groupby("product"):
        g, n = ngr(df)
        L.append(f"| Column chart, {prod}: GGR / NGR | {g:,.2f} / {n:,.2f} |")
    L.append(f"| Table, Registration Bonus: Campaign Bonus Cost / % of NGR | {camp:,.2f} / {camp / ngr_all:.2%} |")
    L += ["", "## Page 2: Player balances", "",
          "| Date slicer end | Player | Balance type | Expected balance |", "|---|---|---|---|"]
    for as_of in [pd.Timestamp("2026-09-06"), dates.date_day.max()]:
        w = wal[wal.transaction_date <= as_of]
        for (pid, bt), v in w.groupby(["player_id", "balance_type"]).signed_amount.sum().items():
            L.append(f"| {as_of.date()} | {pid} | {bt} | {v:,.2f} |")
    L += [f"| Card: Deposits (full range) | | | {wal[wal.txn_type == 'deposit'].amount.sum():,.2f} |",
          "", "## Page 3: Reconciliation", "", "| Visual | Expected |", "|---|---|",
          f"| Card: Settlements Matched Exactly | {(rec.category_type == 'OK').sum()} |",
          f"| Card: Exceptions | {len(exc)} |",
          f"| Card: Act Now Value | {act_now:,.2f} |",
          f"| Card: Bridge Residual | {brg.amount.sum() - brg.gateway_settled_total.max():,.2f} |"]
    running = 0.0
    for _, r in brg.sort_values("step_order").iterrows():
        running += r.amount
        L.append(f"| Waterfall step {r.step_order}: {r.step} | {r.amount:,.2f} (running {running:,.2f}) |")
    L.append(f"| Waterfall total bar | {running:,.2f} (= gateway SETTLED total {brg.gateway_settled_total.max():,.2f}) |")
    for cat, n in exc.category.value_counts().items():
        L.append(f"| Bar, {cat} | {n} |")
    L += ["", "## Page 4: Ingestion monitoring", "", "| Visual | Expected |", "|---|---|",
          f"| Card: Transactions Loaded | {txn.id.nunique():,} |",
          f"| Card: Ingestion Runs | {len(runs)} |",
          f"| Card: Rows Rejected | {runs.rows_rejected.sum()} |",
          f"| Card: API Retries (429 + 500) | {runs.rate_limit_hits.sum() + runs.server_error_hits.sum()} |",
          f"| Run history: new / changed per run | " + " · ".join(
              f"run {r.run_id}: {r.rows_new} / {r.rows_changed}" for r in runs.itertuples()) + " |",
          f"| Run history: statuses | " + " · ".join(f"run {r.run_id} {r.status}" for r in runs.itertuples()) + " |"]
    for st, n in txn.status.value_counts().items():
        L.append(f"| Column, {st} | {n} |")
    rule = lambda bad, bad_colour: f"{bad_colour} (rule)" if bad else "green (rule)"
    L += ["", "## KPI tile colours", "",
          "Status tiles are coloured by a rule on their own value; the others have a fixed colour.", "",
          "| Page | Tile | Expected colour |", "|---|---|---|",
          f"| NGR overview | GGR | {rule(ggr_all < 0, 'red')} |",
          "| NGR overview | Bonus Cost (realised) | amber (fixed: a cost) |",
          f"| NGR overview | NGR | {rule(ngr_all < 0, 'red')} |",
          "| NGR overview | Bonus Liability Outstanding | purple (fixed: owed, not yet a cost) |",
          "| Player balances | Deposits | green (fixed: money in) |",
          "| Reconciliation | Settlements Matched Exactly | green (fixed) |",
          f"| Reconciliation | Exceptions | {rule(len(exc) > 0, 'amber')} |",
          f"| Reconciliation | Act Now Value | {rule(act_now > 0, 'red')} |",
          f"| Reconciliation | Bridge Residual | {rule(abs(brg.amount.sum() - brg.gateway_settled_total.max()) >= 0.005, 'red')} |",
          "| Ingestion monitoring | Transactions Loaded | green (fixed) |",
          "| Ingestion monitoring | Ingestion Runs | navy (fixed: informational) |",
          f"| Ingestion monitoring | Rows Rejected | {rule(runs.rows_rejected.sum() > 0, 'amber')} |",
          "| Ingestion monitoring | API Retries | teal (fixed: informational, retries are handled) |"]
    return "\n".join(L) + "\n"


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
            dax += [f"{n} =", *("    " + line for line in e.split("\n")),
                    f"    -- format: {f}" if f else "    -- hex colour for a KPI tile background", ""]
    (HERE / "measures.dax").write_text("\n".join(dax), encoding="utf-8")
    (HERE / "expected_values.md").write_text(expected_values(), encoding="utf-8")

    n_meas = sum(len(v) for v in MEASURES.values())
    n_vis = sum(len(s["visualContainers"]) for s in report["sections"])
    mode = "DataFolder parameter" if FOLDER_MODE else "data embedded"
    print(f"OK ({mode}): {len(TABLES)} tables, {len(RELATIONSHIPS)} relationships (no ambiguous paths), "
          f"{n_meas} measures, {len(report['sections'])} pages, {n_vis} visuals -- all references resolve")


if __name__ == "__main__":
    main()
