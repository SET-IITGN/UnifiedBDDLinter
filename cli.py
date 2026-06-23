#!/usr/bin/env python3
"""
CLI for UnifiedBDDLinter
"""

import sys
import argparse
import json
from pathlib import Path
from unified_linter import UnifiedLinter, RuleSeverity


def main():
    parser = argparse.ArgumentParser(
        description='Unified BDD Linter - Combines gherkin-lint, cuke_linter, and quality checks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python cli.py my_feature.feature
  python cli.py features/ --format json
  python cli.py features/ --severity error
  python cli.py features/ --summary
        '''
    )
    
    parser.add_argument('path', help='Feature file or directory to lint')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('--severity', choices=['info', 'warning', 'error', 'critical'],
                        help='Minimum severity to report')
    parser.add_argument('--summary', action='store_true',
                        help='Show summary only')
    parser.add_argument('--no-style', action='store_true',
                        help='Disable style rules')
    parser.add_argument('--no-workflow', action='store_true',
                        help='Disable workflow rules')
    
    args = parser.parse_args()
    
    path = Path(args.path)
    linter = UnifiedLinter()
    
    if path.is_file():
        violations = linter.lint_file(str(path))
        results = {str(path): violations}
    elif path.is_dir():
        results = linter.lint_directory(str(path))
    else:
        print(f"Error: {args.path} not found")
        sys.exit(1)
    
    # Filter by severity
    severity_order = {'info': 0, 'warning': 1, 'error': 2, 'critical': 3}
    if args.severity:
        min_severity = severity_order[args.severity]
        for file_path in results:
            results[file_path] = [v for v in results[file_path]
                                   if severity_order[v.severity.value] >= min_severity]

    # Filter out disabled rule families (--no-style / --no-workflow)
    disabled = set()
    if args.no_style:
        disabled.add('style')
    if args.no_workflow:
        disabled.add('workflow')
    if disabled:
        for file_path in results:
            results[file_path] = [v for v in results[file_path]
                                   if v.category not in disabled]

    # Output
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
        for file_path, violations in results.items():
            output['files'][file_path] = linter.format_output(violations, 'json')
        print(json.dumps(output, indent=2))
    else:
        # Text output
        if args.summary:
            print(f"Files checked: {linter.file_count}")
            print(f"Total violations: {total_violations}")
            print(f"Total errors: {total_errors}")
        else:
            for file_path, violations in results.items():
                if violations:
                    print(f"\n{file_path}")
                    print("=" * 80)
                    print(linter.format_output(violations, 'text'))
                else:
                    print(f"{file_path}")
            
            print("\n" + "=" * 80)
            print(f"Summary: {linter.file_count} file(s), {total_violations} violation(s), {total_errors} error(s)")
    
    # Exit with error code if there are errors
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
