# Results

This directory holds the figures from the evaluation, the scripts that draw
them, and a small sample of the measurement data.

## Data

`sample_results.csv` is a 25-row excerpt of the full evaluation output. The full
dataset covers all 20,034 `.feature` files from the 38 repositories and is too
large to keep in the repository (about 550 MB), so it is archived on Zenodo:

> Full dataset: <ZENODO_DOI_URL>  *(add the DOI once the record is published)*

Each row corresponds to one `.feature` file. The 16 columns are:

| Column | Meaning |
| --- | --- |
| `Repository_Name` | source GitHub repository |
| `File_Path` | path of the `.feature` file |
| `Gherkin_Lint_Errors_Before` | gherkin-lint raw output, before fixing |
| `Gherkin_Lint_Errors_Before_nums` | gherkin-lint violation count, before |
| `Cuke_Lint_Errors_Before` | cuke_linter raw output, before |
| `Cuke_Lint_Errors_Before_nums` | cuke_linter violation count, before |
| `BDD_Lint_Errors_Before` | native linter raw output, before |
| `BDD_Lint_Errors_Before_nums` | native violation count, before |
| `Gherkin_Lint_Errors_After` | gherkin-lint raw output, after fixing |
| `Gherkin_Lint_Errors_After_nums` | gherkin-lint violation count, after |
| `Cuke_Lint_Errors_After` | cuke_linter raw output, after |
| `Cuke_Lint_Errors_After_nums` | cuke_linter violation count, after |
| `BDD_Lint_Errors_After` | native linter raw output, after |
| `BDD_Lint_Errors_After_nums` | native violation count, after |
| `Gherkin_Issues_Fixed` | gherkin-lint before minus after |
| `Cuke_Issues_Fixed` | cuke_linter before minus after |

Notes:

- Text columns hold the raw, newline-separated linter output and are empty when
  a file has no violations.
- The `_nums` columns are integer counts. A value of `-1` means the linter
  errored or timed out on that file.
- The three linters use different rule sets and counting granularities, so their
  counts are recorded separately and are not added together.

## Figures

| File | What it shows |
| --- | --- |
| `figures/workflow.svg` | the per-file lint, fix, lint workflow |
| `figures/bdd_pipeline_plot.png` | total violations before and after, per linter |
| `figures/per_repo_reduction.png` | gherkin-lint reduction per repository against size |
| `figures/violations_breakdown.png` | per-rule resolved vs. remaining counts |
| `figures/architecture_diagram.png` | the shared-parse, four-family engine |

The `*_conf.png` variants are alternate renderings produced by the same scripts.

## Regenerating the figures

The plotting scripts read a results CSV and write a PNG:

```
python results/plot_before_after.py
python results/plot_per_repo.py
python results/plot_violations_breakdown.py
```

Edit the `CSV_PATH` near the top of each script to point at your own results
file.
