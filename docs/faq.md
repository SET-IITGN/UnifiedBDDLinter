# Frequently asked questions

These are the questions that came up most often while interpreting the results.
They are worth reading if a number looks surprising. The figures referenced here
live in [../results/figures/](../results/figures/), and the detailed tables are
in [evaluation.md](evaluation.md).

## Why were the other gherkin-lint and native violations not resolved?

Because the residual is almost entirely semantic, and the fixer leaves semantic
rules alone on purpose. The mechanical (form) rules are essentially fully
resolved; what is left is the semantic tail. For gherkin-lint, indentation falls
999,482 to 746 (99.9 percent), and filename, trailing spaces, end-of-file
newline, and duplicate names are nearly fully resolved. What remains is dominated
by semantic rules:

| Linter | Residual rule (semantic) | Remaining |
| --- | --- | ---: |
| gherkin-lint | name-length | 70,072 |
| | only-one-when | 57,756 |
| | keywords-in-logical-order | 26,963 |
| native | multiple-When (W001) | 111,459 |
| | name length (S006) | 102,888 |
| | no verification step (W003) | 40,080 |
| | too-many-steps (W006) | 26,113 |
| | Given/When/Then order (W002) | 21,919 |

Fixing any of these means merging, reordering, renaming, or splitting steps, that
is, rewriting the test's logic. The tool reports them for a human instead.

## Is the filename convention the only cuke_linter issue, and what would fixing it change?

No. cuke_linter flags many rule classes, and the filename rules are only about
7 percent of its violations (21,540 of 302,053). The rest are semantic rules that
form-preserving fixing does not target.

The filename rules are also where the conflict shows up. Renaming files to
kebab-case fixes `FeatureFileWithMismatchedName` (down 9,110) but triggers
`FeatureFileWithInvalidName` (up 10,762), because gherkin-lint wants kebab-case
and cuke_linter wants snake-case. The net effect on filenames is 1,652 worse.

All other (non-filename) cuke rules went from 280,513 to 274,269, that is, 6,244
resolved, led by `StepWithEndPeriod` (637 to 0). Fully resolving the filename
conflict would only move cuke from -1.5 percent to about -2.1 percent, and it
cannot be done without breaking gherkin-lint's requirement. That is the point of
the mutually unsatisfiable conflict. The full per-class table is in
[evaluation.md](evaluation.md).

## Why can the three linters' counts not be added together?

Because they are not measuring the same thing on the same basis:

- Overlap: one defect, such as bad indentation, is flagged by both gherkin-lint
  and the native linter, so summing double-counts it.
- Different rules: each tool checks different things; cuke_linter is mostly
  semantic.
- Different granularity: one tool may emit one violation per file, another one
  per line.
- Independence: the two external linters are used as independent oracles, and
  pooling would destroy the independence that makes the validation meaningful.
- They even conflict, as the filename convention shows.

So each linter is reported separately and never summed. This is also why
gherkin-lint's "before" count (about 1.16 million) differs from the native
linter's (about 1.53 million) on the same files.

## The bar chart shows gherkin "after = 168k". Why, if 99.9 percent is a different number?

The before/after chart has three separate bars, one per linter. The 168k is
gherkin-lint's own after-count (its bar goes 1,163,482 to 167,902). The 99.9
percent number lives in the native linter's results, not gherkin-lint's. They are
different tools counted independently, so the two numbers are on different bars
and are not directly comparable.

## What is the 99.9 percent, and how is 1,222,805 of 1,224,408 computed?

The native linter prints one line per violation, each tagged with a rule id. Count
the form-rule lines (`S001`-`S005` plus `ST00x`) across all files: before is
1,224,408, after is 1,603, so 1,222,805 are resolved, which is 99.9 percent. It is
dominated by `S004` indentation (1,199,929 to 1,003). It is a literal count of
violation lines before and after, not an estimate.

## Is 1,224,408 part of the 1.53 million, and is the leftover semantic?

Yes, with one clarification. The native linter's total splits cleanly:

```text
native total:  1,532,486
  form      1,224,408 -> resolved 1,222,805, left   1,603   (99.9 percent fixed)
  semantic    308,078 -> resolved     657,   left 307,421   (left alone by design)
  total remaining after fixing = 1,603 + 307,421 = 309,024
```

The semantic class by type is 308,078 (about 308K). The 309,024 (about 309K) is
the total still flagged after fixing, which is 1,603 leftover form plus 307,421
semantic. They look similar only because nearly all form was fixed. They are not
the same quantity.

## What does "median 90.7 percent, 27 of 38 exceed 80 percent, none regress" mean?

The 85.6 percent headline is an aggregate weighted by violation count. The
per-repository view proves the result is broad-based rather than propped up by one
large project. Line up the 38 repositories by their reduction; the middle one is
at 90.7 percent. Twenty-seven of the 38 exceed 80 percent, the worst still
improves 32.3 percent, and none regress. The median (90.7 percent, each repository
weighted equally) is higher than the aggregate (85.6 percent), which means the
typical repository does even better than the volume-weighted average. The
per-repository scatter shows this: every point sits high, none below zero, and
there is no downward trend with size.

## Why is the per-repository scatter computed on gherkin-lint only?

gherkin-lint is the best single per-repository oracle. It is independent
(third-party, so not circular like grading with our own linter) and it measures
the form and structural violations the fixer actually targets. cuke_linter is
mostly semantic and conflicted, so a per-repository cuke plot would read flat and
misleading; the native linter would be circular. The before/after bar chart still
shows all three linters in aggregate; the scatter zooms into the one independent,
on-target oracle.
