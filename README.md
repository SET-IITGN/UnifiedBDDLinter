# UnifiedBDDLinter: A Tool to Detect and Remediate Quality Anti-Patterns in Gherkin Feature Files

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20795204-blue.svg)](https://doi.org/10.5281/zenodo.20795204)

A linter and form-preserving auto-fixer for Gherkin `.feature` files.

Gherkin specifications are both human-readable requirements and executable
tests, but their quality is usually policed by a handful of separate, partly
contradictory linters that only report problems and never fix them.
UnifiedBDDLinter brings style, structure, workflow, and business-readability
checks under a single engine, and adds an auto-fixer that repairs the mechanical
issues it finds while leaving anything that would change a test's meaning to a
human.

![Workflow](results/figures/workflow.svg)

## Table of Contents

- [What it checks](#what-it-checks)
- [Installation](#installation)
- [Usage](#usage)
  - [Lint](#lint)
  - [Fix](#fix)
  - [Validate](#validate)
- [How it works](#how-it-works)
- [Results](#results)
- [Documentation](#documentation)
- [Data availability](#data-availability)
- [Repository layout](#repository-layout)
- [A note on the results](#a-note-on-the-results)
- [License](#license)

## What it checks

The linter runs 28 rules across four families:

- **Style**: indentation, trailing whitespace, blank lines, end-of-file newline,
  filename casing.
- **Structure**: feature and scenario names, non-empty files, unique scenario
  names, agreement between the filename and the feature name.
- **Workflow**: Given/When/Then ordering, a single `When` per scenario, the
  presence of an action and a verification step, and step count.
- **Quality (business-readability)**: scenarios that leak implementation detail
  instead of describing business intent, vague language, hardcoded data,
  near-duplicate scenarios, and similar smells.

Eleven of the 28 rules are mechanically fixable; the other seventeen are
detect-only. The full catalog is in [docs/design.md](docs/design.md).

## Installation

```
git clone https://github.com/SET-IITGN/UnifiedBDDLinter.git
cd UnifiedBDDLinter
```

The linter and the auto-fixer need only Python 3 (standard library). The
evaluation harness additionally uses `tqdm` and `matplotlib` for its progress
bar and plots:

```
pip install -r requirements.txt
```

## Usage

Run the commands from the repository root.

### Lint

Lint a file or a directory:

```
python linter.py examples/gmail.feature
python linter.py examples/ --format json
```

`linter.py` runs all four families. A lighter front-end, `cli.py`, runs the
style/structure/workflow subset and is the one the evaluation harness drives; it
also supports `--severity`, `--summary`, and per-family toggles. Pass `--help`
to either for the full set of options.

### Fix

Fix the mechanical issues. The fixer writes to a new directory and never touches
the originals:

```
python auto_fix.py examples/ -o fixed/
```

It repairs only the form-level rules. Anything that would change a scenario's
meaning, such as a missing step, a second `When`, or an over-long name, is
reported but left for a person to resolve.

### Validate

Validate differentially. The harness lints every file with three linters before
and after the fix, using `gherkin-lint` and `cuke_linter` as independent
oracles:

```
python evaluation/phase3_bdd_pipeline_full.py -r <repos-dir> -o out.csv
```

This mode needs `gherkin-lint` (Node.js) and `cuke_linter` (Ruby) on the `PATH`.
The script points at a local install of the two external linters near the top of
the file; adjust those paths for your machine before running it.

## How it works

A single parser scans each file once and builds a line-indexed model that every
rule reads from. The auto-fixer applies an ordered sequence of mechanical,
meaning-preserving edits to a copy of the file. The line between mechanical
repair and human judgement, what gets fixed versus what only gets reported, is
the central design decision. It is described in [docs/design.md](docs/design.md).

## Results

UnifiedBDDLinter was evaluated on 20,034 `.feature` files mined from 38 public
GitHub repositories (the mining pipeline is described in
[docs/evaluation.md](docs/evaluation.md)). With the form-preserving fixer:

- gherkin-lint violations fell 85.6% (1,163,482 to 167,902)
- native violations fell 79.8% (1,532,486 to 309,024)
- 99.8% of files improved, with no regressions
- the median repository saw a 90.7% reduction

![Violations before and after, per linter](results/figures/bdd_pipeline_plot_conf.png)

The result is broad-based rather than driven by a few large projects. Each bubble
below is one repository: size on the horizontal axis, reduction on the vertical,
and the bubble area is the number of violations before fixing.

![Per-repository reduction against size](results/figures/per_repo_reduction_conf.png)

The full per-linter breakdown, the per-repository table for all 38 repositories,
and the command-line reference are in [docs/evaluation.md](docs/evaluation.md).
Common questions about the numbers are answered in [docs/faq.md](docs/faq.md).

## Documentation

The [docs/](docs/) directory carries the detail that does not fit in this README:

- [docs/design.md](docs/design.md) — architecture, the full 28-rule catalog, and
  the safe-fix boundary between what the tool repairs and what it only reports.
- [docs/evaluation.md](docs/evaluation.md) — how the 38-repository corpus was
  collected, the per-linter breakdown, the per-repository table, and the
  command-line parameters.
- [docs/faq.md](docs/faq.md) — answers to the questions that come up most often
  about the numbers: why the residual violations are left untouched, why the
  three linters' counts cannot be added together, what the 99.9% actually
  measures, and the kebab-case versus snake-case filename conflict.

## Data availability

A 25-row excerpt of the per-file before/after measurements is in
[results/sample_results.csv](results/sample_results.csv), and the column meanings
are documented in [results/README.md](results/README.md).

The complete dataset, all 20,034 rows, is too large for this repository (about
550 MB) and is archived on Zenodo:

> Full dataset (Zenodo): [Zenodo Dataset](https://zenodo.org/records/20795204)
>
> Video demonstration: [Tool Demo](https://www.youtube.com/watch?v=xtSa8xjaRp4)

## Repository layout

```
UnifiedBDDLinter/
|-- linter.py              full four-family linter
|-- cli.py                 lighter CLI (style/structure/workflow subset)
|-- unified_linter.py      shared parser and rule engine (cli.py + linter.py)
|-- auto_fix.py            form-preserving auto-fixer
|-- .unified-lintrc.json   rule severities and toggles
|-- evaluation/
|   `-- phase3_bdd_pipeline_full.py    differential lint-fix-lint harness
|-- results/
|   |-- figures/           workflow, before/after, per-repository, per-rule
|   |-- plot_*.py          scripts that draw the figures
|   |-- sample_results.csv 25-row excerpt of the measurements
|   `-- README.md          column dictionary and the dataset link
|-- examples/              a few sample .feature files
|-- docs/
|   |-- design.md          architecture, rule catalog, safe-fix boundary
|   |-- evaluation.md      corpus, per-linter analysis, per-repository table
|   `-- faq.md             questions about the numbers
|-- requirements.txt
`-- LICENSE
```

## A note on the results

The numbers above come from one corpus of 38 repositories. How much the fixer
reduces depends on the starting quality of the `.feature` files, which varies a
great deal between projects, so results on a different repository or corpus will
differ. The figures characterize the tool on real-world code rather than promise
a fixed percentage on any given project.

## License

Released under the MIT License. See [LICENSE](LICENSE).
