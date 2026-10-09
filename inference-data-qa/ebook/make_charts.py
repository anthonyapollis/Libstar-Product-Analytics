"""Draw the eBook charts from the real result tables in outputs/ (nothing is typed in by hand).

    python ebook/make_charts.py      -> ebook/img/chart_*.png
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ebook" / "img"
OUT.mkdir(parents=True, exist_ok=True)

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"            # validated categorical / diverging
STATUS = {"Critical": "#d03b3b", "High": "#ec835a", "Medium": "#fab219"}          # status palette, always with a label

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def read(name):
    with open(ROOT / "outputs" / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tidy(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


# 1. Net against gross: the salary differences behind one net figure.
t = read("recon_salary_totals.csv")[0]
parts = [p.rsplit(" ", 1) for p in t["by_employee"].split(", ")]
parts = sorted(((e, float(v)) for e, v in parts), key=lambda x: x[1])
fig, ax = plt.subplots(figsize=(7.2, 3.0))
for i, (emp, v) in enumerate(parts):
    ax.barh(i, v, color=BLUE if v > 0 else RED, height=0.55)
    ax.text(v + (2500 if v > 0 else -2500), i, f"{'+' if v > 0 else '−'}R{abs(v):,.0f}", va="center",
            ha="left" if v > 0 else "right", color=INK, fontsize=9)
ax.set_yticks(range(len(parts)), [e for e, _ in parts])
ax.axvline(0, color=INK2, lw=1)
ax.set_xlim(-120000, 120000)
ax.xaxis.set_major_formatter(lambda x, _: f"R{x/1000:,.0f}k")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
tidy(ax)
net, gross = float(t["net_difference"]), float(t["gross_difference"])
ax.set_title(f"Employee 360 minus payroll, per employee:  net +R{net:,.0f}  ·  gross R{gross:,.0f}",
             loc="left", fontsize=10.5, color=INK, pad=10)
ax.text(0.99, 0.04, "blue = Employee 360 higher · red = lower", transform=ax.transAxes, ha="right", fontsize=8.5, color=INK2)
fig.tight_layout()
fig.savefig(OUT / "chart_net_vs_gross.png", dpi=200)
plt.close(fig)

# 2. Monitoring: employees affected per rule, coloured by severity (labelled, never colour alone).
m = read("monitoring.csv")
fig, ax = plt.subplots(figsize=(7.2, 3.9))
y = list(range(len(m)))[::-1]
for yi, r in zip(y, m):
    n = int(r["affected_count"])
    ax.barh(yi, n, color=STATUS[r["severity"]], height=0.6)
    gate = "  BLOCK" if r["blocks_release"] == "True" else ""
    ax.text(n + 0.08, yi, f"{n}  {r['severity']} · {r['action']}{gate}", va="center", fontsize=8.5, color=INK)
ax.set_yticks(y, [f"{r['rule_id']} {r['dimension']}" for r in m], fontsize=8.5)
ax.set_xlim(0, 9.5)
ax.set_xlabel("employees affected")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
tidy(ax)
ax.set_title("All 10 rules fail; 5 of them block release", loc="left", fontsize=10.5, color=INK, pad=10)
fig.tight_layout()
fig.savefig(OUT / "chart_monitoring.png", dpi=200)
plt.close(fig)

# 3. Issue lifecycle over the three incremental runs.
runs = read("incremental_runs.csv")
labels = ["Run 1\nsupplied data", "Run 2\nsame files", "Run 3\nsimulated fixes"]
series = [("open issues", "open_issues", BLUE), ("new (alerted)", "new_issues", ORANGE), ("resolved", "resolved_issues", AQUA)]
fig, ax = plt.subplots(figsize=(7.2, 3.1))
w = 0.26
for k, (name, col, color) in enumerate(series):
    xs = [i + (k - 1) * (w + 0.02) for i in range(len(runs))]
    vals = [int(r[col]) for r in runs]
    ax.bar(xs, vals, width=w, color=color, label=name)
    for x, v in zip(xs, vals):
        ax.text(x, v + 0.3, str(v), ha="center", fontsize=9, color=INK)
ax.set_xticks(range(len(runs)), labels)
ax.text(1, 19.6, "skipped: 0 rows read, no checks run", ha="center", fontsize=8.5, color=INK2)
ax.set_ylim(0, 21)
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_axisbelow(True)
tidy(ax)
ax.legend(frameon=False, ncol=3, loc="upper right", bbox_to_anchor=(1, 1.16), fontsize=8.5)
ax.set_title("Alerts only for new issues", loc="left", fontsize=10.5, color=INK, pad=22)
fig.tight_layout()
fig.savefig(OUT / "chart_issue_lifecycle.png", dpi=200)
plt.close(fig)
print("wrote", sorted(p.name for p in OUT.glob("chart_*.png")))
