"""Merge the per-sheet Qlik object files into ONE combined array and upgrade
presentation to the proven Qlik Sense client rendering pattern.

Why one file: posting sheets and their child objects in separate `qlik app
object set` calls makes the CLI silently re-link sheet cells to blank
auto-generated duplicates. Everything must ship in a single call.

Upgrades applied to every chart:
- explicit `color` block (varied accents per chart; stacked/pie/treemap left
  on auto so Sense colours by dimension)
- `dataPoint.showLabels`, `gridLine.auto`, `legend`
- sorting via measure `qSortBy.qSortByNumeric` + `qInterColumnSortOrder`
  (dimension qSortCriterias expressions are ignored by the client)
"""

import json
import os

QDIR = os.path.join(os.path.dirname(__file__), "..", "qlik", "objects")
SHEET_FILES = [
    "sheet1_executive.json",
    "sheet2_category_brand.json",
    "sheet3_regional_channel.json",
    "sheet4_data_quality.json",
    "sheet5_ml_insights.json",
]
OUT = os.path.join(QDIR, "app_objects_combined.json")

# single-accent colour per chart id (varied across the app, navy/teal family)
ACCENT = {
    "line-growth": "#1B2A4A",
    "bar-cat-margin": "#2A9D8F",
    "bar-province-revenue": "#1B2A4A",
    "bar-province-skus": "#2A9D8F",
    "bar-channel-revenue": "#264653",
    "bar-reject": "#E76F51",
}
# multi-dim / categorical charts: auto colour by dimension + legend
BY_DIMENSION = {"pie-group", "treemap-cat", "bar-brands", "bar-cat-solution",
                "scatter-segments"}


def upgrade(obj: dict) -> dict:
    qid = obj["qInfo"]["qId"]
    qtype = obj["qInfo"]["qType"]
    if qtype in ("sheet", "kpi", "filterpane", "text-image", "table"):
        return obj

    if qid in ACCENT:
        obj["color"] = {"mode": "primary",
                        "primary": {"color": {"index": -1, "color": ACCENT[qid]}}}
        obj["legend"] = {"show": False}
    elif qid in BY_DIMENSION:
        obj["legend"] = {"show": True, "dock": "auto", "showTitle": True}

    obj["dataPoint"] = {"showLabels": True}
    obj["gridLine"] = {"auto": True}

    cube = obj.get("qHyperCubeDef")
    if cube:
        ndims = len(cube.get("qDimensions", []))
        nmeas = len(cube.get("qMeasures", []))
        # strip client-ignored dimension sort expressions
        for d in cube.get("qDimensions", []):
            d.get("qDef", {}).pop("qSortCriterias", None)
        # sort by first measure, descending (skip time series)
        if ndims and nmeas and qid != "line-growth":
            cube["qMeasures"][0]["qSortBy"] = {"qSortByNumeric": -1}
            cube["qInterColumnSortOrder"] = (
                [ndims] + list(range(ndims)) + list(range(ndims + 1, ndims + nmeas)))
        else:
            cube["qInterColumnSortOrder"] = list(range(ndims + nmeas))
    return obj


def main() -> None:
    combined, seen = [], set()
    for f in SHEET_FILES:
        for obj in json.load(open(os.path.join(QDIR, f), encoding="utf-8")):
            qid = obj["qInfo"]["qId"]
            if qid in seen:
                raise SystemExit(f"duplicate object id across sheets: {qid}")
            seen.add(qid)
            combined.append(upgrade(obj))
    json.dump(combined, open(OUT, "w", encoding="utf-8"), indent=1)
    sheets = sum(1 for o in combined if o["qInfo"]["qType"] == "sheet")
    print(f"combined: {len(combined)} objects ({sheets} sheets) -> {OUT}")


if __name__ == "__main__":
    main()
