#!/usr/bin/env python3
"""
plot_before_after.py  ->  results/bdd_pipeline_plot_conf.png

Grouped bar chart of total violations BEFORE vs AFTER auto-fix, for the three
linters (gherkin-lint, cuke_linter, UnifiedBDDLinter), read from the pipeline CSV.

This version can be made *self-contained* (so a separate results table is not
needed): turn on SHOW_VALUE_LABELS to print the exact count on each bar, and
SHOW_RUN_HEALTH to print a one-line run summary under the axes.

Run:  python3 plot_before_after.py
Edit the CONFIG block below to play with colours, legend, labels, size, etc.
"""

import csv
import sys
import matplotlib
matplotlib.use("Agg")                      # headless; remove if you want a window
import matplotlib.pyplot as plt
import numpy as np

# ============================== CONFIG (tweak me) ==============================
CSV_PATH   = "bdd_pipeline_results.csv"    # path to the results CSV (same dir)
OUT_PATH   = "bdd_pipeline_plot_conf.png"  # set to "bdd_pipeline_plot.png" for the paper
DPI        = 150
FIGSIZE    = (8.4, 5.2)

# x-axis groups: (display label, CSV "before" column, CSV "after" column)
GROUPS = [
    ("gherkin-lint", "Gherkin_Lint_Errors_Before_nums", "Gherkin_Lint_Errors_After_nums"),
    ("cuke_linter",  "Cuke_Lint_Errors_Before_nums",    "Cuke_Lint_Errors_After_nums"),
    ("BDD-lint",     "BDD_Lint_Errors_Before_nums",      "BDD_Lint_Errors_After_nums"),
]

BAR_WIDTH      = 0.36
COLOR_BEFORE   = "#d95f02"                  # orange
COLOR_AFTER    = "#1b9e77"                  # green
LABEL_BEFORE   = "Before"
LABEL_AFTER    = "After"

YLABEL         = "Total violations"
TITLE          = "Before vs After Auto-Fix — full corpus"
SHOW_TITLE     = True

# Legend ----------------------------------------------------------------------
LEGEND_SHOW    = True
LEGEND_LOC     = "upper right"              # e.g. "upper left", "best", (x,y)
LEGEND_NCOL    = 1
LEGEND_FONTSZ  = 11
LEGEND_FRAME   = True

# Percentage-change annotation above the "after" bar --------------------------
SHOW_PCT       = True
PCT_FONTSZ     = 10.5
PCT_DY_POINTS  = 34                         # vertical offset of the % label

# Exact count label ON each bar (makes a separate results table unnecessary) --
SHOW_VALUE_LABELS = True
VALUE_LABEL_STYLE = "short"                 # "short" -> 1.16M / 168k ; "full" -> 1,163,482
VALUE_FONTSZ      = 9

# One-line run-health summary under the axes (the old table footer) -----------
SHOW_RUN_HEALTH = True
FIX_FAILURES    = 15                        # from the run log (not in the CSV)
TOOL_ERRORS     = 0                         # from the run log (not in the CSV)
HEALTH_FONTSZ   = 8.5
# =============================================================================


def total(rows, col):
    s = 0
    for r in rows:
        try:
            s += max(0, int(r[col]))        # clamp tool-error sentinels (-1) to 0
        except (ValueError, TypeError, KeyError):
            pass
    return s


def fmt(n):
    if VALUE_LABEL_STYLE == "full":
        return f"{n:,}"
    return f"{n/1e6:.2f}M" if n >= 1e6 else (f"{n/1e3:.0f}k" if n >= 1000 else str(n))


def file_outcomes(rows):
    """Improved / unchanged / regressed counts, from native BDD before-after."""
    imp = unch = reg = 0
    for r in rows:
        try:
            d = int(r["BDD_Lint_Errors_Before_nums"]) - int(r["BDD_Lint_Errors_After_nums"])
        except (ValueError, TypeError, KeyError):
            continue
        imp += d > 0
        unch += d == 0
        reg += d < 0
    return imp, unch, reg


def main():
    csv.field_size_limit(sys.maxsize)       # cells hold long violation text
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    labels  = [g[0] for g in GROUPS]
    before  = [total(rows, g[1]) for g in GROUPS]
    after   = [total(rows, g[2]) for g in GROUPS]
    x       = np.arange(len(GROUPS))
    ymax    = max(before + [1])

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars_b = ax.bar(x - BAR_WIDTH / 2, before, BAR_WIDTH, label=LABEL_BEFORE, color=COLOR_BEFORE)
    bars_a = ax.bar(x + BAR_WIDTH / 2, after,  BAR_WIDTH, label=LABEL_AFTER,  color=COLOR_AFTER)

    if SHOW_VALUE_LABELS:
        for bar, val in list(zip(bars_b, before)) + list(zip(bars_a, after)):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.012,
                    fmt(val), ha="center", va="bottom",
                    fontsize=VALUE_FONTSZ, fontweight="bold")

    if SHOW_PCT:
        for i, (b, a) in enumerate(zip(before, after)):
            if b == 0:
                continue
            pct = (b - a) / b * 100
            sign = "-" if pct >= 0 else "+"
            ax.annotate(f"{sign}{abs(pct):.1f}%",
                        xy=(i + BAR_WIDTH / 2, a),
                        xytext=(0, PCT_DY_POINTS), textcoords="offset points",
                        ha="center", fontsize=PCT_FONTSZ, fontweight="bold",
                        color=COLOR_AFTER if pct >= 0 else COLOR_BEFORE)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel(YLABEL)
    if SHOW_TITLE:
        ax.set_title(f"{TITLE}  ({len(rows):,} .feature files)", fontweight="bold")
    ax.set_ylim(0, ymax * 1.22)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))

    if LEGEND_SHOW:
        ax.legend(loc=LEGEND_LOC, ncol=LEGEND_NCOL, fontsize=LEGEND_FONTSZ,
                  frameon=LEGEND_FRAME)

    rect = [0, 0, 1, 1]
    if SHOW_RUN_HEALTH:
        imp, _unch, reg = file_outcomes(rows)
        n = max(1, len(rows))
        health = (f"{len(rows):,} files  ·  {imp/n*100:.1f}% improved  ·  {reg} regressed  ·  "
                  f"{FIX_FAILURES} auto-fix failures  ·  {TOOL_ERRORS} tool errors")
        fig.text(0.5, 0.005, health, ha="center", fontsize=HEALTH_FONTSZ,
                 style="italic", color="#555555")
        rect = [0, 0.03, 1, 1]

    fig.tight_layout(rect=rect)
    fig.savefig(OUT_PATH, dpi=DPI)
    print(f"saved {OUT_PATH}  |  before={before}  after={after}")


if __name__ == "__main__":
    main()
