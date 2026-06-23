#!/usr/bin/env python3
"""
plot_violations_breakdown.py  ->  results/violations_breakdown_conf.png

Per-rule horizontal stacked bars for the native linter (UnifiedBDDLinter):
  green  = resolved   (before - after)
  orange = remaining  (after)
  red /  = regression (rule got worse after fixing)
Read from the pipeline CSV.

Run:  python3 plot_violations_breakdown.py
Edit the CONFIG block below to play with colours, legend, #rules shown, etc.
"""

import csv
import sys
import re
from collections import Counter
import matplotlib
matplotlib.use("Agg")                      # headless; remove if you want a window
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ============================== CONFIG (tweak me) ==============================
CSV_PATH    = "results/sample_results.csv"  # sample shipped with the repo; swap for the full Zenodo CSV
OUT_PATH    = "violations_breakdown_conf.png"
DPI         = 150
FIGSIZE     = (9, 5.2)

# Which native columns hold the per-rule violation text (rule id starts each line)
BEFORE_TEXT = "BDD_Lint_Errors_Before"
AFTER_TEXT  = "BDD_Lint_Errors_After"
RULE_REGEX  = r"^(SY\d+|ST\d+|S\d+|W\d+|Q\d+)\b"

TOP_N       = 8                            # how many rules (by 'before') to show
X_MAX       = 1.45e6                        # x-axis upper limit
XLABEL      = "Violation count"
TITLE       = ("BDD-lint per-rule: raised vs resolved\n"
               "green = resolved   orange = remaining   red-hatch = regression")
SHOW_TITLE  = True

COLOR_SOLVED    = "#1b9e77"                 # green
COLOR_REMAINING = "#d95f02"                 # orange
COLOR_REGRESS   = "#b2182b"                 # red
REGRESS_HATCH   = "//"
LABEL_FONTSZ    = 8.5                       # the "Sxxx: a->b (pct)" text

# Legend ----------------------------------------------------------------------
LEGEND_SHOW    = True
LEGEND_LOC     = "lower right"              # "upper right", "best", (x,y), ...
LEGEND_FONTSZ  = 9
LEGEND_FRAME   = True
# =============================================================================


def tally(rows, col):
    c = Counter()
    for r in rows:
        for ln in r[col].splitlines():
            m = re.match(RULE_REGEX, ln)
            if m:
                c[m.group(1)] += 1
    return c


def main():
    csv.field_size_limit(sys.maxsize)
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    before = tally(rows, BEFORE_TEXT)
    after  = tally(rows, AFTER_TEXT)
    order  = sorted(before, key=lambda k: -before[k])[:TOP_N]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    y = np.arange(len(order))[::-1]
    for yi, ru in zip(y, order):
        raised = before[ru]
        solved = before[ru] - after[ru]
        if solved >= 0:
            ax.barh(yi, solved, color=COLOR_SOLVED)
            ax.barh(yi, raised - solved, left=solved, color=COLOR_REMAINING)
        else:                              # regression: got worse after fixing
            ax.barh(yi, raised, color=COLOR_REMAINING)
            ax.barh(yi, abs(solved), left=raised, color=COLOR_REGRESS, hatch=REGRESS_HATCH)
        pct = solved / raised * 100 if raised else 0
        ax.text(max(raised, raised - solved) + 8000, yi,
                f"{ru}: {before[ru]:,}→{after[ru]:,} ({pct:+.0f}%)",
                va="center", fontsize=LABEL_FONTSZ)

    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=9)
    ax.set_xlim(0, X_MAX)
    ax.set_xlabel(XLABEL)
    if SHOW_TITLE:
        ax.set_title(TITLE, fontweight="bold", fontsize=11)
    ax.grid(axis="x", ls="--", alpha=0.4)

    if LEGEND_SHOW:
        handles = [
            mpatches.Patch(color=COLOR_SOLVED, label="resolved"),
            mpatches.Patch(color=COLOR_REMAINING, label="remaining"),
            mpatches.Patch(facecolor=COLOR_REGRESS, hatch=REGRESS_HATCH, label="regression"),
        ]
        ax.legend(handles=handles, loc=LEGEND_LOC, fontsize=LEGEND_FONTSZ,
                  frameon=LEGEND_FRAME)

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=DPI)
    print(f"saved {OUT_PATH}  |  rules shown: {order}")


if __name__ == "__main__":
    main()
