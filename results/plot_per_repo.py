#!/usr/bin/env python3
"""
plot_per_repo.py  ->  results/per_repo_reduction.png

Scatter of per-repository gherkin-lint violation reduction (%) vs repository
size (number of .feature files, log x-axis). Marker size encodes the number of
violations before fixing; colour encodes the reduction. A dashed line marks the
median. Read from the pipeline CSV.

Run:  python3 plot_per_repo.py
Edit the CONFIG block below to play with colours, colourbar, legend, size, etc.
"""

import csv
import sys
import statistics
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")                      # headless; remove if you want a window
import matplotlib.pyplot as plt
import numpy as np

# ============================== CONFIG (tweak me) ==============================
CSV_PATH    = "results/sample_results.csv"  # sample shipped with the repo; swap for the full Zenodo CSV
OUT_PATH    = "per_repo_reduction_conf.png"
DPI         = 150
FIGSIZE     = (8.4, 5.2)

# Which linter's reduction to plot per repo: (before col, after col, axis label)
BEFORE_COL  = "Gherkin_Lint_Errors_Before_nums"
AFTER_COL   = "Gherkin_Lint_Errors_After_nums"
YLABEL      = "gherkin-lint violation reduction (%)"

CMAP        = "RdYlGn"                      # try "viridis", "RdYlGn", "coolwarm"
CMAP_VMIN   = 0
CMAP_VMAX   = 100
EDGECOLOR   = "#333333"
MARKER_ALPHA = 0.85

# Marker size scaling: size = clip(before / SIZE_DIV, SIZE_MIN, SIZE_MAX)
SIZE_DIV    = 200
SIZE_MIN    = 25
SIZE_MAX    = 600

XLABEL      = "Repository size  (number of .feature files, log scale)"
TITLE       = "Auto-fix efficacy vs. repository size"
SHOW_TITLE  = True
YLIM        = (-5, 103)

# Reference lines -------------------------------------------------------------
SHOW_MEDIAN_LINE = True
SHOW_80_LINE     = True                     # dotted line at 80%

# Colourbar (acts as the "legend" for colour) ---------------------------------
SHOW_COLORBAR    = True
COLORBAR_LABEL   = "reduction (%)"

# Optional: also draw a size legend (marker-size key). Off by default.
SHOW_SIZE_LEGEND = False
SIZE_LEGEND_VALUES = [1000, 10000, 50000]   # "violations before" reference points
SIZE_LEGEND_LOC    = "lower right"
# =============================================================================


def num(r, c):
    try:
        return max(0, int(r[c]))
    except (ValueError, TypeError, KeyError):
        return 0


def main():
    csv.field_size_limit(sys.maxsize)
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    by_repo = defaultdict(list)
    for r in rows:
        by_repo[r["Repository_Name"]].append(r)

    sizes, reductions, befores = [], [], []
    for repo, rs in by_repo.items():
        b = sum(num(r, BEFORE_COL) for r in rs)
        a = sum(num(r, AFTER_COL) for r in rs)
        if b > 0:                           # skip repos with no violations to reduce
            sizes.append(len(rs))
            reductions.append((b - a) / b * 100)
            befores.append(b)

    sizes   = np.array(sizes)
    reds    = np.array(reductions)
    befores = np.array(befores)
    med     = statistics.median(reds)
    msize   = np.clip(befores / SIZE_DIV, SIZE_MIN, SIZE_MAX)

    fig, ax = plt.subplots(figsize=FIGSIZE)
    sc = ax.scatter(sizes, reds, s=msize, c=reds, cmap=CMAP,
                    vmin=CMAP_VMIN, vmax=CMAP_VMAX,
                    edgecolors=EDGECOLOR, linewidths=0.7, alpha=MARKER_ALPHA, zorder=3)

    if SHOW_MEDIAN_LINE:
        ax.axhline(med, ls="--", color="#444444", lw=1.4)
        ax.text(sizes.min(), med + 1.5, f"median = {med:.1f}%",
                fontsize=10, fontweight="bold", color="#444444", va="bottom")
    if SHOW_80_LINE:
        ax.axhline(80, ls=":", color="gray", lw=1)

    ax.set_xscale("log")
    ax.set_xlabel(XLABEL, fontsize=11)
    ax.set_ylabel(YLABEL, fontsize=11)
    ax.set_ylim(*YLIM)
    if SHOW_TITLE:
        ax.set_title(f"{TITLE}  ({len(reds)} repositories, {len(rows):,} files)",
                     fontsize=11, fontweight="bold")
    ax.grid(True, which="both", ls="--", alpha=0.35, zorder=0)

    if SHOW_COLORBAR:
        fig.colorbar(sc, ax=ax, label=COLORBAR_LABEL)

    if SHOW_SIZE_LEGEND:
        handles = [plt.scatter([], [], s=np.clip(v / SIZE_DIV, SIZE_MIN, SIZE_MAX),
                               color="gray", edgecolors=EDGECOLOR,
                               label=f"{v:,} violations")
                   for v in SIZE_LEGEND_VALUES]
        ax.legend(handles=handles, loc=SIZE_LEGEND_LOC, labelspacing=1.4,
                  borderpad=1.0, fontsize=8, title="marker size")

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=DPI, bbox_inches="tight")
    print(f"saved {OUT_PATH}  |  {len(reds)} repos  median={med:.1f}%  "
          f"min={reds.min():.1f}%  regressing={(reds < 0).sum()}")


if __name__ == "__main__":
    main()
