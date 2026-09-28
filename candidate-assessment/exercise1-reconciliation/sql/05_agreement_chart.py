"""Figure: three independent implementations agree on every reconciliation category.

Reads ../evidence/agreement_by_category.csv (written by 04_independent_check.py)
and draws two panels sharing the category axis: exception rows, and financial
impact in NAD. Each category has three bars (MySQL script, dbt model, pandas
re-implementation). Equal bars are the point: any disagreement would show as a
visibly different bar and a missing check mark.
Usage: python 05_agreement_chart.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Reference palette (dataviz skill), categorical slots 1-3, light surface. Validated:
# CVD dE 9.2, normal-vision dE 27.6; aqua is < 3:1 on the surface, so every group
# carries a direct value label and the legend names each series.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SERIES = [("sql", "MySQL script", "#2a78d6"), ("dbt", "dbt model", "#eb6834"),
          ("pandas", "Independent pandas code", "#1baf7a")]
LABELS = {
    "failed_but_settled": "Settled, marked FAILED", "unrecognised": "Unrecognised settlement",
    "timing_prior": "Prior-period deposit", "dup_internal": "Duplicate internal deposit",
    "dup_gateway": "Duplicate gateway row", "timing_next": "Settles next period",
    "missing_settlement": "No settlement found", "reversal": "Reversal / chargeback",
    "fee": "Fee above contract", "net": "Net ≠ gross − fee", "amount": "Gross amount differs",
    "rounding": "Rounding ≤ 1 cent",
}

df = pd.read_csv("../evidence/agreement_by_category.csv")
ok = df[df.short == "ok"].iloc[0]
df = df[df.short != "ok"].sort_values(["n_sql", "rand_sql"], ascending=[True, True]).reset_index(drop=True)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 7.2), sharey=True,
                               gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.08})
fig.patch.set_facecolor(SURFACE)
h, gap = 0.24, 0.02          # thin bars with a small surface gap between them

for ax, metric, fmt in [(ax1, "n", "{:.0f}"), (ax2, "rand", "{:,.2f}")]:
    ax.set_facecolor(SURFACE)
    for i, (key, _, color) in enumerate(SERIES):
        y = df.index + (1 - i) * (h + gap)
        ax.barh(y, df[f"{metric}_{key}"], height=h, color=color, edgecolor=SURFACE, linewidth=1, zorder=3)
    # one direct label per group: the three values are identical, so label once
    lim = max(df[f"{metric}_sql"].max(), 1)
    for idx, v in enumerate(df[f"{metric}_sql"]):
        x = max(v, 0) + lim * 0.015
        ax.text(x, idx, fmt.format(v), va="center", ha="left", fontsize=9, color=INK2, zorder=4)
    ax.axvline(0, color=INK2, linewidth=0.8, zorder=2)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)

ax1.set_xlim(0, df.n_sql.max() * 1.18)
ax1.set_xlabel("Exception rows")
lo, hi = df.rand_sql.min(), df.rand_sql.max()
ax2.set_xlim(min(lo * 1.25, 0), hi * 1.22)
ax2.set_xlabel("Financial impact (NAD)")
ax2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax1.set_yticks(df.index)
ax1.set_yticklabels([LABELS[s] for s in df.short])

# agreement column: a check mark per row, plus a plain-text word so it isn't symbol-only
for idx, agree in enumerate(df.agree):
    ax2.text(1.02, idx, "✓ agree" if agree else "✗ differ", transform=ax2.get_yaxis_transform(),
             va="center", ha="left", fontsize=9.5, color=INK if agree else "#d03b3d", fontweight="bold")

handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in SERIES]
fig.legend(handles, [lab for _, lab, _ in SERIES], loc="upper left", bbox_to_anchor=(0.012, 0.905),
           ncol=3, frameon=False, fontsize=10, handlelength=1.2, columnspacing=1.6)
fig.text(0.012, 0.975, "Three separate implementations agree on every reconciliation category",
         fontsize=15, fontweight="bold", color=INK, va="top")
fig.text(0.012, 0.935, f"Rows and rand impact per exception category. Clean matches: "
         f"{ok.n_sql:.0f} · {ok.n_dbt:.0f} · {ok.n_pandas:.0f}. All 317 rows also agree one-by-one.",
         fontsize=10.5, color=INK2, va="top")
fig.subplots_adjust(left=0.19, right=0.91, top=0.83, bottom=0.09)
out = "../screenshots/02_three_way_agreement.png"
fig.savefig(out, dpi=160, facecolor=SURFACE)
print("wrote", out)
