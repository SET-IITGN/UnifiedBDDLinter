# Design notes

## Architecture

UnifiedBDDLinter is built around a single shared model. A `UnifiedParser` scans
a `.feature` file once, builds a line-indexed representation (keyword matching
and indentation counting), and every rule reads from that same representation.
This keeps the rules cheap and independent: each is a small, stateless check that
returns a uniform `Violation` record with a line, a rule id, a severity, a
message, and a category.

The parser is a line-based scanner, not a full grammar or AST. That is a
deliberate trade-off. It keeps the tool small and fast and is enough for the
mechanical and stylistic rules that make up most of the catalog. A proper
Gherkin AST is the natural next step for deeper semantic checks.

## Rule catalog

Twenty-eight rules across four families. `F` marks a rule the auto-fixer can
repair without changing meaning; `D` marks a detect-only rule that is reported
for a human. Eleven rules are fixable, seventeen are detect-only.

### Style

| Id | Checks | |
| --- | --- | --- |
| S001 | No trailing whitespace | F |
| S002 | No multiple blank lines | F |
| S003 | Final newline at end of file | F |
| S004 | Two-space indentation | F |
| S005 | Kebab-case filename | F |
| S006 | Name length within limit | D |

### Structure

| Id | Checks | |
| --- | --- | --- |
| ST001 | Feature is named | F |
| ST002 | Scenario is named | F |
| ST003 | File is non-empty | D |
| ST004 | Feature element present | F |
| ST005 | Background is non-empty | D |
| ST006 | Unique scenario names | F |
| ST007 | Filename matches the feature name | F |

### Workflow

| Id | Checks | |
| --- | --- | --- |
| W001 | A single `When` per scenario | D |
| W002 | Given/When/Then order | D |
| W003 | Has a `Then` (verification) | D |
| W004 | Has a `When` (action) | D |
| W005 | No trailing period on steps | F |
| W006 | Step count within limit | D |

### Quality (business-readability)

| Id | Checks | |
| --- | --- | --- |
| Q001 | No implementation-detail leakage | D |
| Q002 | No vague language | D |
| Q003 | Sensible step count | D |
| Q004 | No test jargon in scenarios | D |
| Q005 | Descriptive scenario name | D |
| Q006 | No hardcoded or mock data | D |
| Q007 | Clear negation | D |
| Q008 | No near-duplicate scenarios | D |
| SY001 | Spelling | D |

The Quality rules are lexical heuristics. Q001, for example, flags a step whose
text contains a UI-action keyword (`clicks`, `selects`, `button`, `input field`,
and so on) as leaking implementation detail rather than describing business
intent. They are keyword and pattern matches, not deep semantic analysis.

## The safe-fix boundary

The auto-fixer only touches form-level rules: indentation, whitespace, blank
lines, end-of-file newline, filename casing, and the structural naming rules. It
applies an ordered sequence of edits to a copy of the file and never modifies the
input.

Everything that would require guessing intent is left alone. Injecting a missing
`Then`, choosing which of two `When` steps to keep, or shortening an over-long
name all change what a scenario means, so those rules stay detect-only. The fixer
reports them for a person to handle. This boundary between mechanical repair and
human judgement is the central design decision of the tool.

## Two linter entry points

Both front-ends run the same engine in `unified_linter.py`; they differ only in
how many rule families they enable.

- `linter.py` runs the engine in full mode: all four families, including the
  Quality (business-readability) rules. This is the complete 28-rule linter.
- `cli.py` runs the style, structure, and workflow subset. This is the path the
  evaluation harness uses, because those are the rules whose effect the two
  external linters can independently confirm.

Because they share one engine, they agree exactly on the rules they have in
common; `linter.py` simply enables more.

## Differential validation

The evaluation harness (`evaluation/phase3_bdd_pipeline_full.py`) runs a per-file
loop: lint the original with all three linters, apply the fixer to a copy,
re-lint the copy, and record the before and after counts. `gherkin-lint` and
`cuke_linter` act as independent oracles. A fix is trustworthy only when their
counts fall or hold and never rise.

Because no external linter checks business readability, the Quality family has no
oracle to corroborate it and is therefore reported but kept out of the
differential measurements.
