#!/usr/bin/env python3
"""
phase3_bdd_pipeline_full.py  —  BDD Linting, Auto-Fix & Validation Pipeline
============================================================================
Part of the UnifiedBDDLinter project.

For every ``.feature`` file inside the cloned-repositories tree this script:

    1. Lints the file with THREE linters and records both the raw
       violation text *and* a numeric count (BEFORE auto-fix):
          - gherkin-lint  (Node.js CLI)
          - cuke_linter   (Ruby gem)
          - UnifiedBDDLinter / "BDD-lint"  (our cli.py, JSON mode)
    2. Runs ``auto_fix.py`` (UnifiedBDDLinter) to repair the file. The
       fixed copy is written to a temp dir so the original is untouched.
    3. Re-lints the fixed copy with the same three linters (AFTER auto-fix).
    4. Appends one fully-populated row to a CSV.
    5. Renders a grouped bar chart comparing total issues before vs after.

Violation-text cells preserve each tool's raw, newline-separated output
(gherkin-lint rows verbatim; the full cuke_linter block including file:line
locations; BDD-lint as "RULE Ln: message" lines) so the CSV matches the
reference format produced by bdd_trilinter_pipeline.py.

CSV columns (16):
    Repository_Name, File_Path,
    Gherkin_Lint_Errors_Before, Gherkin_Lint_Errors_Before_nums,
    Cuke_Lint_Errors_Before,    Cuke_Lint_Errors_Before_nums,
    BDD_Lint_Errors_Before,     BDD_Lint_Errors_Before_nums,
    Gherkin_Lint_Errors_After,  Gherkin_Lint_Errors_After_nums,
    Cuke_Lint_Errors_After,     Cuke_Lint_Errors_After_nums,
    BDD_Lint_Errors_After,      BDD_Lint_Errors_After_nums,
    Gherkin_Issues_Fixed   (= Gherkin_Before_nums - Gherkin_After_nums),
    Cuke_Issues_Fixed      (= Cuke_Before_nums    - Cuke_After_nums)

Usage:
    python3 phase3_bdd_pipeline_full.py --sample 10   # dry-run on 10 files
    python3 phase3_bdd_pipeline_full.py               # full run
    python3 phase3_bdd_pipeline_full.py --plot-only   # rebuild chart from CSV
    python3 phase3_bdd_pipeline_full.py -n 50 -o /tmp/out.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# ── tqdm: real-time progress bar (graceful fallback if not installed) ────────
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:                                     # pragma: no cover
    TQDM_AVAILABLE = False

    def tqdm(iterable, **kwargs):  # type: ignore[misc]
        return iterable

# ── matplotlib / seaborn: visualisation (graceful fallback) ─────────────────
try:
    import matplotlib
    matplotlib.use("Agg")          # headless backend — safe on servers
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOT_AVAILABLE = True
except ImportError:                                     # pragma: no cover
    PLOT_AVAILABLE = False


# ============================================================================
# CONFIGURATION  —  adjust these absolute paths if your environment differs
# ============================================================================

# Root directory that contains all cloned repositories (source sub-dirs inside)
REPOS_ROOT = Path(
    "/home/vaishnavkoka/RE4BDD/Phase-workout-for-bdd"
    "/phase-3 (refinement)/phase-3-part-2-cloning"
)

# UnifiedBDDLinter project directory (holds auto_fix.py and cli.py)
UNIFIED_DIR     = Path("/home/vaishnavkoka/RE4BDD/UnifiedBDDLinter")
AUTO_FIX_SCRIPT = UNIFIED_DIR / "auto_fix.py"
BDD_LINT_CLI    = UNIFIED_DIR / "cli.py"

# gherkin-lint binary (Node.js) and its configuration file
GHERKIN_LINT_BIN = Path(
    "/home/vaishnavkoka/RE4BDD/gherkin-cli/node_modules/.bin/gherkin-lint"
)
GHERKIN_LINT_RC = Path("/home/vaishnavkoka/RE4BDD/gherkin-cli/.gherkin-lintrc")

# cuke_linter is on PATH; it auto-reads .cukelinter from its CWD, so we always
# launch it with cwd=GHERKIN_CLI_DIR where the project config lives.
CUKE_LINTER_BIN = "cuke_linter"
GHERKIN_CLI_DIR = Path("/home/vaishnavkoka/RE4BDD/gherkin-cli")

# Output artefacts land OUTSIDE the read-only phase folders.
OUTPUT_DIR   = Path("/home/vaishnavkoka/RE4BDD/bdd_pipeline_output")
DEFAULT_CSV  = OUTPUT_DIR / "bdd_linting_pipeline_full_results.csv"
DEFAULT_PLOT = OUTPUT_DIR / "bdd_linting_pipeline_full_plot.png"

# Per-subprocess timeout in seconds (raise it for very large feature files)
TOOL_TIMEOUT = 60

# ANSI colour-escape pattern, used to strip CLI colour codes before parsing
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# Ordered list of CSV column names — DO NOT reorder (downstream tools rely on it)
CSV_FIELDNAMES = [
    "Repository_Name",
    "File_Path",
    "Gherkin_Lint_Errors_Before",
    "Gherkin_Lint_Errors_Before_nums",
    "Cuke_Lint_Errors_Before",
    "Cuke_Lint_Errors_Before_nums",
    "BDD_Lint_Errors_Before",
    "BDD_Lint_Errors_Before_nums",
    "Gherkin_Lint_Errors_After",
    "Gherkin_Lint_Errors_After_nums",
    "Cuke_Lint_Errors_After",
    "Cuke_Lint_Errors_After_nums",
    "BDD_Lint_Errors_After",
    "BDD_Lint_Errors_After_nums",
    "Gherkin_Issues_Fixed",
    "Cuke_Issues_Fixed",
]

# Sentinel string written to a *text* cell when a linter fails to run at all.
TOOL_ERROR_TEXT = "<TOOL_ERROR>"


# ============================================================================
# STEP 0 — TOOL AVAILABILITY CHECK
# ============================================================================

def check_tools() -> dict:
    """Verify every required tool/script is reachable; print and return status."""
    checks = {
        "auto_fix.py":     AUTO_FIX_SCRIPT.is_file(),
        "BDD-lint (cli)":  BDD_LINT_CLI.is_file(),
        "gherkin-lint":    GHERKIN_LINT_BIN.is_file(),
        "gherkin-lintrc":  GHERKIN_LINT_RC.is_file(),
        "cuke_linter":     shutil.which(CUKE_LINTER_BIN) is not None,
    }
    for name, ok in checks.items():
        print(f"    [{'OK' if ok else 'MISSING'}] {name}")
    return checks


# ============================================================================
# STEP 1 — FILE DISCOVERY
# ============================================================================

def find_feature_files(root: Path, sample_size: Optional[int] = None) -> list:
    """
    Recursively find ``.feature`` files under *root*.

    Skips symlinks and anything inside a hidden directory component (e.g. .git).
    When *sample_size* is given, return only the first N files (dry-run mode).
    """
    files: list = []
    for path in sorted(root.rglob("*.feature")):
        if path.is_symlink():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        files.append(path)
        if sample_size and len(files) >= sample_size:
            break
    return files


def repo_name_from_path(file_path: Path, root: Path) -> str:
    """
    Derive the repository name from a cloned feature-file path.

    Layout:  <root>/<source_dir>/<repo_name>/.../<file>.feature
    Returns the <repo_name> component; falls back to the parent dir name.
    """
    try:
        parts = file_path.relative_to(root).parts
        return parts[1] if len(parts) >= 2 else parts[0]
    except ValueError:
        return file_path.parent.name


# ============================================================================
# STEP 2 — LINTING HELPERS
# Each linter returns (violation_text: str, count: int).
# On a tool failure it returns (TOOL_ERROR_TEXT, -1).
# Violation text is the tool's raw, newline-separated output.
# ============================================================================

def _strip_ansi(text: str) -> str:
    """Remove ANSI colour-escape codes from terminal output."""
    return _ANSI_ESCAPE.sub("", text)


def run_gherkin_lint(feature_file: Path) -> Tuple[str, int]:
    """
    Run gherkin-lint on a single file.

    Violation rows look like:  '  12   Some message    rule-name'
    (leading whitespace + line number + message + rule). We keep each such row
    verbatim (column spacing preserved), newline-joined, and count them.
    """
    cmd = [str(GHERKIN_LINT_BIN), "--config", str(GHERKIN_LINT_RC), str(feature_file)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT
        )
    except FileNotFoundError:
        print(f"\n  [ERROR] gherkin-lint binary not found: {GHERKIN_LINT_BIN}",
              file=sys.stderr)
        return TOOL_ERROR_TEXT, -1
    except subprocess.TimeoutExpired:
        print(f"\n  [WARN] gherkin-lint timed out on {feature_file.name}",
              file=sys.stderr)
        return TOOL_ERROR_TEXT, -1
    except Exception as exc:                            # pragma: no cover
        print(f"\n  [ERROR] gherkin-lint unexpected error: {exc}", file=sys.stderr)
        return TOOL_ERROR_TEXT, -1

    cleaned = _strip_ansi(result.stdout + result.stderr)
    violations = [
        line.strip()
        for line in cleaned.splitlines()
        if re.match(r"^\s+\d+\s+\S", line)
    ]
    return "\n".join(violations), len(violations)


def run_cuke_linter(feature_file: Path) -> Tuple[str, int]:
    """
    Run cuke_linter on a single file (cwd = GHERKIN_CLI_DIR so it finds config).

    Output groups issues under a Linter-class header followed by an indented
    message and an indented file:line location, then a trailing summary line
    'N issues found'.  The count comes from that summary; the violation TEXT is
    the full raw block printed before it (indentation and locations preserved).
    """
    cmd = [CUKE_LINTER_BIN, "-p", str(feature_file)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=TOOL_TIMEOUT, cwd=str(GHERKIN_CLI_DIR),
        )
    except FileNotFoundError:
        print("\n  [ERROR] cuke_linter not found on PATH.", file=sys.stderr)
        return TOOL_ERROR_TEXT, -1
    except subprocess.TimeoutExpired:
        print(f"\n  [WARN] cuke_linter timed out on {feature_file.name}",
              file=sys.stderr)
        return TOOL_ERROR_TEXT, -1
    except Exception as exc:                            # pragma: no cover
        print(f"\n  [ERROR] cuke_linter unexpected error: {exc}", file=sys.stderr)
        return TOOL_ERROR_TEXT, -1

    output = _strip_ansi(result.stdout + result.stderr)
    match  = re.search(r"(\d+)\s+issues?\s+found", output)
    count  = int(match.group(1)) if match else 0
    text   = output[:match.start()].strip() if match else output.strip()
    return text, count


def run_bdd_lint(feature_file: Path) -> Tuple[str, int]:
    """
    Run the UnifiedBDDLinter ("BDD-lint") via cli.py in JSON mode.

    cli.py is launched with cwd=UNIFIED_DIR so its 'import unified_linter'
    resolves.  We read summary.total_violations for the count and flatten each
    violation into a 'RULE Ln: message' line, newline-joined.
    """
    cmd = [sys.executable, str(BDD_LINT_CLI), str(feature_file), "--format", "json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=TOOL_TIMEOUT, cwd=str(UNIFIED_DIR),
        )
    except FileNotFoundError:
        print(f"\n  [ERROR] BDD-lint cli.py not found: {BDD_LINT_CLI}",
              file=sys.stderr)
        return TOOL_ERROR_TEXT, -1
    except subprocess.TimeoutExpired:
        print(f"\n  [WARN] BDD-lint timed out on {feature_file.name}",
              file=sys.stderr)
        return TOOL_ERROR_TEXT, -1
    except Exception as exc:                            # pragma: no cover
        print(f"\n  [ERROR] BDD-lint unexpected error: {exc}", file=sys.stderr)
        return TOOL_ERROR_TEXT, -1

    # cli.py exits 1 when errors are present — that is normal, so parse stdout.
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        # Corrupted feature file or unexpected output: report 0 with raw note.
        note = _strip_ansi((result.stdout + result.stderr)).strip()
        return note, 0

    count = int(data.get("summary", {}).get("total_violations", 0))

    violations: list = []
    for _fpath, raw_list in data.get("files", {}).items():
        # Per-file value is itself a JSON-encoded string (see cli.py).
        try:
            items = json.loads(raw_list) if isinstance(raw_list, str) else raw_list
        except json.JSONDecodeError:
            continue
        for v in items:
            violations.append(
                f"{v.get('rule', '?')} L{v.get('line', '?')}: {v.get('message', '')}"
            )

    return "\n".join(violations), count


# ============================================================================
# STEP 3 — AUTO-FIX
# ============================================================================

def run_auto_fix(feature_file: Path, output_dir: Path) -> Optional[Path]:
    """
    Run auto_fix.py on *feature_file*, writing the fixed copy to *output_dir*.
    The original file is NEVER modified.

    auto_fix.py may rename the output (kebab-case rule), so we clear the dir
    first and return whatever single ``.feature`` file appears afterward.
    """
    for existing in output_dir.glob("*"):
        try:
            existing.unlink()
        except OSError:
            pass

    cmd = [
        sys.executable, str(AUTO_FIX_SCRIPT),
        str(feature_file), "--output", str(output_dir),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True,
                       timeout=TOOL_TIMEOUT, cwd=str(UNIFIED_DIR))
    except subprocess.TimeoutExpired:
        print(f"\n  [WARN] auto_fix.py timed out on {feature_file.name}",
              file=sys.stderr)
        return None
    except Exception as exc:                            # pragma: no cover
        print(f"\n  [ERROR] auto_fix.py crashed: {exc}", file=sys.stderr)
        return None

    fixed = list(output_dir.glob("*.feature"))
    return fixed[0] if fixed else None


# ============================================================================
# STEP 4 — CSV LOGGING
# ============================================================================

def ensure_csv_header(csv_path: Path) -> None:
    """Write the header row if the CSV does not yet exist or is empty."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES).writeheader()


def append_csv_row(csv_path: Path, row: dict) -> None:
    """Append a single result row to the CSV."""
    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES).writerow(row)


def already_processed_files(csv_path: Path) -> set:
    """Return File_Path values already in the CSV (enables resume)."""
    done: set = set()
    if csv_path.exists() and csv_path.stat().st_size > 0:
        with open(csv_path, "r", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                done.add(row.get("File_Path", ""))
    return done


# ============================================================================
# PER-FILE WORKER  (safe to run concurrently — uses a private temp dir)
# ============================================================================

def process_one_file(feature_file: Path, repos_root: Path) -> dict:
    """
    Run the full BEFORE → auto-fix → AFTER pipeline for a single file and
    return its CSV row plus per-file stats.

    Each call uses its OWN temporary directory for the auto-fixed copy, so
    many invocations can run in parallel without colliding. The temp dir is
    always removed before returning.
    """
    repo = repo_name_from_path(feature_file, repos_root)
    fixed_tmp = Path(tempfile.mkdtemp(prefix="bdd_fix_"))
    try:
        # ── Phase 1: lint BEFORE (3 linters) ─────────────────────────────
        gl_b_txt, gl_b_n = run_gherkin_lint(feature_file)
        ck_b_txt, ck_b_n = run_cuke_linter(feature_file)
        bd_b_txt, bd_b_n = run_bdd_lint(feature_file)
        tool_error = 1 if -1 in (gl_b_n, ck_b_n, bd_b_n) else 0

        # ── Phase 2: auto-fix into this task's private temp dir ──────────
        fixed_file = run_auto_fix(feature_file, fixed_tmp)
        fix_failed = 1 if fixed_file is None else 0
        target = feature_file if fixed_file is None else fixed_file

        # ── Phase 3: lint AFTER (3 linters) ──────────────────────────────
        gl_a_txt, gl_a_n = run_gherkin_lint(target)
        ck_a_txt, ck_a_n = run_cuke_linter(target)
        bd_a_txt, bd_a_n = run_bdd_lint(target)
    finally:
        shutil.rmtree(fixed_tmp, ignore_errors=True)

    # ── Deltas (treat -1 tool errors as 0 for safe arithmetic) ───────────
    gl_fixed = max(0, gl_b_n) - max(0, gl_a_n)
    ck_fixed = max(0, ck_b_n) - max(0, ck_a_n)

    row = {
        "Repository_Name":                 repo,
        "File_Path":                       str(feature_file),
        "Gherkin_Lint_Errors_Before":      gl_b_txt,
        "Gherkin_Lint_Errors_Before_nums": gl_b_n,
        "Cuke_Lint_Errors_Before":         ck_b_txt,
        "Cuke_Lint_Errors_Before_nums":    ck_b_n,
        "BDD_Lint_Errors_Before":          bd_b_txt,
        "BDD_Lint_Errors_Before_nums":     bd_b_n,
        "Gherkin_Lint_Errors_After":       gl_a_txt,
        "Gherkin_Lint_Errors_After_nums":  gl_a_n,
        "Cuke_Lint_Errors_After":          ck_a_txt,
        "Cuke_Lint_Errors_After_nums":     ck_a_n,
        "BDD_Lint_Errors_After":           bd_a_txt,
        "BDD_Lint_Errors_After_nums":      bd_a_n,
        "Gherkin_Issues_Fixed":            gl_fixed,
        "Cuke_Issues_Fixed":               ck_fixed,
    }
    return {
        "row":        row,
        "fix_failed": fix_failed,
        "tool_error": tool_error,
        "gl_fixed":   max(0, gl_fixed),
        "cl_fixed":   max(0, ck_fixed),
        "bdd_fixed":  max(0, max(0, bd_b_n) - max(0, bd_a_n)),
    }


# ============================================================================
# MAIN PIPELINE ORCHESTRATOR
# ============================================================================

def run_pipeline(repos_root: Path, csv_path: Path,
                 sample_size: Optional[int] = None,
                 workers: int = 1) -> None:
    """Run the full before → auto-fix → after pipeline for every feature file."""
    print("\n" + "=" * 70)
    print("  BDD Linting, Auto-Fix & Validation Pipeline  (3 linters)")
    print("=" * 70)
    print(f"  Repos root : {repos_root}")
    print(f"  Output CSV : {csv_path}")
    print(f"  Mode       : "
          f"{'SAMPLE (' + str(sample_size) + ' files)' if sample_size else 'FULL RUN'}\n")

    # ── 0. Tool check ────────────────────────────────────────────────────
    print("[Step 0] Checking required tools ...")
    missing = [k for k, ok in check_tools().items() if not ok]
    if missing:
        print(f"\n  The following tools are missing: {missing}")
        print("  Fix the CONFIGURATION section at the top of this script.")
        sys.exit(1)
    print("  All tools found.\n")

    # ── 1. Discover feature files ────────────────────────────────────────
    print("[Step 1] Discovering .feature files ...")
    all_files = find_feature_files(repos_root, sample_size)
    print(f"  Found {len(all_files):,} file(s).\n")
    if not all_files:
        print("  Nothing to process. Verify REPOS_ROOT.")
        return

    # ── 2. Resume support ────────────────────────────────────────────────
    ensure_csv_header(csv_path)
    done    = already_processed_files(csv_path)
    pending = [f for f in all_files if str(f) not in done]
    if done:
        print(f"[Resume] {len(done):,} already processed, "
              f"{len(pending):,} remaining.\n")
    if not pending:
        print("  All files already processed. Use --plot-only to rebuild chart.")
        return

    # ── 3. Process (parallel across workers, or sequential) ──────────────
    print(f"[Step 2-4] Processing {len(pending):,} file(s) "
          f"with {workers} worker(s) ...\n")

    stats = {"processed": 0, "fix_failed": 0, "tool_errors": 0,
             "gl_fixed": 0, "cl_fixed": 0, "bdd_fixed": 0}

    def _accumulate(result: dict) -> None:
        """Write one result row to the CSV and fold its stats in (main thread)."""
        append_csv_row(csv_path, result["row"])
        stats["processed"] += 1
        stats["fix_failed"]  += result["fix_failed"]
        stats["tool_errors"] += result["tool_error"]
        stats["gl_fixed"]    += result["gl_fixed"]
        stats["cl_fixed"]    += result["cl_fixed"]
        stats["bdd_fixed"]   += result["bdd_fixed"]

    progress = tqdm(total=len(pending), desc="Linting", unit="file", ncols=88,
                    colour="green")
    try:
        if workers <= 1:
            for feature_file in pending:
                _accumulate(process_one_file(feature_file, repos_root))
                progress.update(1)
        else:
            # Threads suffice: each task is dominated by external subprocesses,
            # which release the GIL. The CSV is written only on the main thread
            # (as futures complete), so no file lock is required.
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(process_one_file, f, repos_root): f
                           for f in pending}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        _accumulate(fut.result())
                    except Exception as exc:                # pragma: no cover
                        print(f"\n  [ERROR] worker failed on "
                              f"{futures[fut].name}: {exc}", file=sys.stderr)
                    progress.update(1)
    finally:
        progress.close()

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("  Pipeline Complete")
    print("-" * 70)
    print(f"  Files processed        : {stats['processed']:,}")
    print(f"  Auto-fix failures      : {stats['fix_failed']:,}")
    print(f"  Files with tool errors : {stats['tool_errors']:,}")
    print(f"  Gherkin issues fixed   : {stats['gl_fixed']:,}")
    print(f"  Cuke issues fixed      : {stats['cl_fixed']:,}")
    print(f"  BDD-lint issues fixed  : {stats['bdd_fixed']:,}")
    print(f"  CSV written to         : {csv_path}\n")


# ============================================================================
# STEP 5 — DATA VISUALISATION
# ============================================================================

def plot_results(csv_path: Path, plot_path: Path) -> None:
    """
    Read the CSV and render a grouped bar chart of total issues Before vs
    After auto-fix for gherkin-lint, cuke-lint and BDD-lint.
    """
    if not PLOT_AVAILABLE:
        print("[WARN] matplotlib/seaborn not installed — skipping plot.")
        print("       Install with:  pip install matplotlib seaborn")
        return
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        print(f"[WARN] No data at {csv_path}. Run the pipeline first.")
        return

    num_cols = [
        "Gherkin_Lint_Errors_Before_nums", "Gherkin_Lint_Errors_After_nums",
        "Cuke_Lint_Errors_Before_nums",    "Cuke_Lint_Errors_After_nums",
        "BDD_Lint_Errors_Before_nums",     "BDD_Lint_Errors_After_nums",
    ]
    totals = {c: 0 for c in num_cols}
    n_rows = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n_rows += 1
            for c in num_cols:
                try:
                    totals[c] += max(0, int(row.get(c, 0)))  # -1 errors → 0
                except (ValueError, TypeError):
                    pass
    if n_rows == 0:
        print("[WARN] CSV had no data rows.")
        return

    categories  = ["Gherkin-Lint", "Cuke-Lint", "BDD-Lint"]
    before_vals = [totals["Gherkin_Lint_Errors_Before_nums"],
                   totals["Cuke_Lint_Errors_Before_nums"],
                   totals["BDD_Lint_Errors_Before_nums"]]
    after_vals  = [totals["Gherkin_Lint_Errors_After_nums"],
                   totals["Cuke_Lint_Errors_After_nums"],
                   totals["BDD_Lint_Errors_After_nums"]]
    y_max = max(before_vals + after_vals + [1])

    sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    x_pos, bar_w = list(range(len(categories))), 0.34

    bars_b = ax.bar([x - bar_w / 2 for x in x_pos], before_vals, bar_w,
                    label="Before Auto-Fix", color="#d95f02", alpha=0.9, zorder=3)
    bars_a = ax.bar([x + bar_w / 2 for x in x_pos], after_vals, bar_w,
                    label="After Auto-Fix",  color="#1b9e77", alpha=0.9, zorder=3)

    for bar in list(bars_b) + list(bars_a):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + y_max * 0.012,
                f"{int(bar.get_height()):,}",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    for i, (bv, av) in enumerate(zip(before_vals, after_vals)):
        if bv > 0:
            pct = (bv - av) / bv * 100
            arrow, colour = ("down", "#1b9e77") if pct >= 0 else ("up", "#d95f02")
            ax.annotate(f"{arrow} {abs(pct):.1f}%",
                        xy=(i + bar_w / 2 + 0.02, av + y_max * 0.05),
                        fontsize=10, color=colour, fontweight="bold")

    ax.set_xticks(x_pos)
    ax.set_xticklabels(categories, fontsize=12)
    ax.set_ylabel("Total Issues", fontsize=12)
    ax.set_title("BDD Lint Issues Before vs After UnifiedBDDLinter Auto-Fix\n"
                 f"({n_rows:,} feature files, 3 linters)",
                 fontsize=13, fontweight="bold", pad=14)
    ax.legend(fontsize=11, loc="upper right")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_ylim(0, y_max * 1.18)
    ax.grid(axis="y", linestyle="--", alpha=0.6, zorder=0)

    plt.tight_layout()
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(plot_path), dpi=150)
    plt.close(fig)
    print(f"[Step 5] Plot saved to: {plot_path}")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BDD Linting, Auto-Fix & Validation Pipeline (3 linters)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run — validate parsing/CSV/plot on 10 files first:
  python3 phase3_bdd_pipeline_full.py --sample 10

  # Full run on every cloned feature file:
  python3 phase3_bdd_pipeline_full.py

  # Rebuild the chart from an existing CSV (no re-linting):
  python3 phase3_bdd_pipeline_full.py --plot-only
""",
    )
    parser.add_argument("--repos-root", "-r", default=str(REPOS_ROOT), metavar="DIR",
                        help="Root directory of cloned repositories")
    parser.add_argument("--output-csv", "-o", default=str(DEFAULT_CSV), metavar="FILE",
                        help="Path for the results CSV")
    parser.add_argument("--plot-path", default=str(DEFAULT_PLOT), metavar="FILE",
                        help="Path for the output PNG plot")
    parser.add_argument("--sample", "-n", type=int, default=None, metavar="N",
                        help="Process only the first N files (dry-run / validation)")
    parser.add_argument("--workers", "-w", type=int, default=1, metavar="N",
                        help="Parallel worker threads (default 1). Each file is "
                             "independent; try 12-20 for the full corpus.")
    parser.add_argument("--plot-only", action="store_true",
                        help="Skip the pipeline; rebuild the plot from an existing CSV")
    args = parser.parse_args()

    csv_path  = Path(args.output_csv)
    plot_path = Path(args.plot_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if args.plot_only:
        print("[--plot-only] Reading existing CSV ...")
        plot_results(csv_path, plot_path)
        return

    run_pipeline(Path(args.repos_root), csv_path, args.sample, args.workers)
    plot_results(csv_path, plot_path)


if __name__ == "__main__":
    main()
