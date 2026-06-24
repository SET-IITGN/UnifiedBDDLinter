#!/usr/bin/env python3
"""
linter.py - The complete UnifiedBDDLinter (all four families, 28 rules).

This is a thin front-end over the single shared engine in `unified_linter.py`,
run in *full* mode. It is the SAME engine that `cli.py` and the evaluation
harness use; `cli.py` runs the oracle-checkable Style/Structure/Workflow subset
(the rules the differential study measures), while `linter.py` additionally
reports the ST007 filename rule and the novel Quality (business-readability)
family. One engine, one parse, 28 rules.
"""

import sys
import argparse
import json
from pathlib import Path
from unified_linter import UnifiedLinter, RuleSeverity


def main():
    parser = argparse.ArgumentParser(
        description='UnifiedBDDLinter - complete 28-rule linter '
                    '(Style, Structure, Workflow, Quality)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python linter.py my_feature.feature
  python linter.py features/ --format json
  python linter.py features/ --severity error
  python linter.py features/ --summary
        '''
    )
    parser.add_argument('path', help='Feature file or directory to lint')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('--severity', choices=['info', 'warning', 'error', 'critical'],
                        help='Minimum severity to report')
    parser.add_argument('--summary', action='store_true',
                        help='Show summary only')
    args = parser.parse_args()

    path = Path(args.path)
    linter = UnifiedLinter(full=True)   # all four families, 28 rules

    if path.is_file():
        results = {str(path): linter.lint_file(str(path))}
    elif path.is_dir():
        results = linter.lint_directory(str(path))
    else:
        print(f"Error: {args.path} not found")
        sys.exit(1)

    severity_order = {'info': 0, 'warning': 1, 'error': 2, 'critical': 3}
    if args.severity:
        min_severity = severity_order[args.severity]
        for fp in results:
            results[fp] = [v for v in results[fp]
                           if severity_order[v.severity.value] >= min_severity]

    total_violations = sum(len(v) for v in results.values())
    total_errors = sum(len([x for x in v if x.severity == RuleSeverity.ERROR])
                       for v in results.values())

    if args.format == 'json':
        output = {
            'summary': {
                'total_files': linter.file_count,
                'total_violations': total_violations,
                'total_errors': total_errors,
            },
            'files': {}
        }
        for fp, violations in results.items():
            output['files'][fp] = linter.format_output(violations, 'json')
        print(json.dumps(output, indent=2))
    else:
        if args.summary:
            print(f"Files checked: {linter.file_count}")
            print(f"Total violations: {total_violations}")
            print(f"Total errors: {total_errors}")
        else:
            for fp, violations in results.items():
                if violations:
                    print(f"\n{fp}")
                    print("=" * 80)
                    print(linter.format_output(violations, 'text'))
                else:
                    print(f"{fp}")
            print("\n" + "=" * 80)
            print(f"Summary: {linter.file_count} file(s), "
                  f"{total_violations} violation(s), {total_errors} error(s)")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
