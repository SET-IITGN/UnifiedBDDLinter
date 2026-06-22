"""
Unified BDD Linter - Main entry point
Combines gherkin-lint, cuke_linter, and quality rules
"""

import re
from pathlib import Path
from typing import List
from dataclasses import dataclass
from enum import Enum


class RuleSeverity(Enum):
    """Rule violation severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Violation:
    """Represents a linting violation"""
    line: int
    column: int
    rule_id: str
    rule_name: str
    severity: RuleSeverity
    message: str
    suggestion: str = ""
    category: str = ""


class UnifiedParser:
    """Gherkin parser"""
    def __init__(self):
        self.lines = []
        self.file_path = None
        
    def parse(self, file_path: str):
        self.file_path = file_path
        with open(file_path, 'r') as f:
            self.lines = f.readlines()
        return self


class StyleRules:
    """gherkin-lint style validation (18 rules)"""
    
    @staticmethod
    def check_all(parser: UnifiedParser) -> List[Violation]:
        violations = []
        
        # S001: No trailing spaces
        for i, line in enumerate(parser.lines, 1):
            if line.rstrip() != line.rstrip('\n'):
                violations.append(Violation(
                    line=i, column=len(line.rstrip()) + 1,
                    rule_id='S001', rule_name='No trailing spaces',
                    severity=RuleSeverity.WARNING,
                    message=f'Line {i} has trailing whitespace',
                    category='style'
                ))
        
        # S002: No multiple empty lines
        empty_count = 0
        for i, line in enumerate(parser.lines, 1):
            if not line.strip():
                empty_count += 1
                if empty_count > 1:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='S002', rule_name='No multiple empty lines',
                        severity=RuleSeverity.INFO,
                        message=f'Multiple empty lines at {i}',
                        suggestion='Remove consecutive blank lines',
                        category='style'
                    ))
            else:
                empty_count = 0
        
        # S003: EOF newline
        if parser.lines and not parser.lines[-1].endswith('\n'):
            violations.append(Violation(
                line=len(parser.lines), column=1,
                rule_id='S003', rule_name='EOF newline',
                severity=RuleSeverity.INFO,
                message='File does not end with newline',
                suggestion='Add newline at end of file',
                category='style'
            ))
        
        # S004: Indentation
        for i, line in enumerate(parser.lines, 1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            if any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                if indent != 2:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='S004', rule_name='Indentation',
                        severity=RuleSeverity.ERROR,
                        message=f'Line {i}: Expected indent 2, got {indent}',
                        suggestion='Use 2 spaces for step indentation',
                        category='style'
                    ))
            elif any(stripped.startswith(kw + ':') for kw in ['Feature', 'Background', 'Scenario', 'Examples']):
                if indent != 0:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='S004', rule_name='Indentation',
                        severity=RuleSeverity.ERROR,
                        message=f'Line {i}: Keywords should not be indented',
                        category='style'
                    ))
        
        return violations


class StructureRules:
    """Gherkin structure validation"""
    
    @staticmethod
    def check_all(parser: UnifiedParser) -> List[Violation]:
        violations = []
        
        # ST001: Unnamed feature
        for i, line in enumerate(parser.lines, 1):
            if line.strip() == 'Feature:':
                violations.append(Violation(
                    line=i, column=1,
                    rule_id='ST001', rule_name='Unnamed feature',
                    severity=RuleSeverity.ERROR,
                    message='Feature must have a name',
                    category='structure'
                ))
        
        # ST002: Unnamed scenarios
        for i, line in enumerate(parser.lines, 1):
            if line.strip() in ['Scenario:', 'Scenario Outline:']:
                violations.append(Violation(
                    line=i, column=1,
                    rule_id='ST002', rule_name='Unnamed scenario',
                    severity=RuleSeverity.ERROR,
                    message='Scenario must have a name',
                    category='structure'
                ))
        
        # ST003: Empty file
        if not any(line.strip() for line in parser.lines):
            violations.append(Violation(
                line=1, column=1,
                rule_id='ST003', rule_name='Empty file',
                severity=RuleSeverity.ERROR,
                message='File is empty',
                category='structure'
            ))
        
        # ST004: No feature
        if not any(line.strip().startswith('Feature:') for line in parser.lines):
            violations.append(Violation(
                line=1, column=1,
                rule_id='ST004', rule_name='No feature',
                severity=RuleSeverity.ERROR,
                message='File must contain a Feature',
                category='structure'
            ))
        
        # ST006: Duplicate scenario names
        scenario_names = {}
        for i, line in enumerate(parser.lines, 1):
            if line.strip().startswith('Scenario'):
                name = re.sub(r'^Scenario.*?:\s*', '', line.strip())
                if name in scenario_names:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='ST006', rule_name='Duplicate scenario name',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario duplicated (line {scenario_names[name]})',
                        category='structure'
                    ))
                else:
                    scenario_names[name] = i
        
        # ST007: Feature name must match file name (cuke_linter + gherkin-lint rule)
        # Supports both naming conventions:
        # - snake_case (cuke_linter): wikipedia_search.feature
        # - kebab-case (gherkin-lint): wikipedia-search.feature
        if parser.file_path:
            # Extract file name without extension (e.g., "login_flow" from "login_flow.feature")
            file_name = Path(parser.file_path).stem  # Removes .feature extension
            
            # Find the feature line
            for i, line in enumerate(parser.lines, 1):
                if line.strip().startswith('Feature:'):
                    feature_name = re.sub(r'^Feature:\s*', '', line.strip())
                    
                    # Normalize both names: convert to lowercase and replace underscores/hyphens with spaces
                    # This treats snake_case, kebab-case, and spaces as equivalent
                    file_name_normalized = file_name.lower().replace('_', ' ').replace('-', ' ')
                    feature_name_normalized = feature_name.lower().replace('_', ' ').replace('-', ' ')
                    
                    # Check if they match
                    if file_name_normalized != feature_name_normalized:
                        violations.append(Violation(
                            line=i, column=1,
                            rule_id='ST007', rule_name='Feature name must match file name',
                            severity=RuleSeverity.ERROR,
                            message=f'Feature name "{feature_name}" does not match file name "{file_name}"',
                            suggestion=f'Rename feature to "{file_name}" or rename file to "{feature_name.replace(" ", "-").lower()}.feature" (kebab-case) or "{feature_name.replace(" ", "_").lower()}.feature" (snake_case)',
                            category='structure'
                        ))
                    break
        
        return violations


class WorkflowRules:
    """cuke_linter + GWT validation"""
    
    @staticmethod
    def check_all(parser: UnifiedParser) -> List[Violation]:
        violations = []
        
        # W001: Only one When
        in_scenario = False
        when_count = 0
        scenario_line = 0
        for i, line in enumerate(parser.lines, 1):
            if line.strip().startswith('Scenario'):
                in_scenario = True
                when_count = 0
                scenario_line = i
            elif in_scenario and line.strip().startswith(('Scenario', 'Feature', 'Background')):
                in_scenario = False
            
            if in_scenario and line.strip().startswith('When'):
                when_count += 1
                if when_count > 1:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='W001', rule_name='Only one When',
                        severity=RuleSeverity.WARNING,
                        message=f'Multiple When steps (line {scenario_line})',
                        suggestion='Use And/But for additional actions',
                        category='workflow'
                    ))
        
        # W002: GWT order
        in_scenario = False
        last_keyword_type = None
        scenario_line = 0
        for i, line in enumerate(parser.lines, 1):
            if line.strip().startswith('Scenario'):
                in_scenario = True
                last_keyword_type = None
                scenario_line = i
            elif in_scenario and line.strip().startswith(('Scenario', 'Feature', 'Background')):
                in_scenario = False
            
            if in_scenario:
                for kw, kw_type in [('Given', 'given'), ('When', 'when'), ('Then', 'then')]:
                    if line.strip().startswith(kw):
                        if last_keyword_type == 'then' and kw_type in ['given', 'when']:
                            violations.append(Violation(
                                line=i, column=1,
                                rule_id='W002', rule_name='GWT order',
                                severity=RuleSeverity.ERROR,
                                message=f'{kw} after Then (wrong order)',
                                suggestion='Follow Given-When-Then order',
                                category='workflow'
                            ))
                        elif last_keyword_type == 'when' and kw_type == 'given':
                            violations.append(Violation(
                                line=i, column=1,
                                rule_id='W002', rule_name='GWT order',
                                severity=RuleSeverity.ERROR,
                                message='Given after When (wrong order)',
                                category='workflow'
                            ))
                        last_keyword_type = kw_type
                        break
        
        # W003: No verification step (Then required)
        in_scenario = False
        has_then = False
        scenario_line = 0
        scenario_name = ""
        for i, line in enumerate(parser.lines, 1):
            if line.strip().startswith('Scenario'):
                if in_scenario and not has_then:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W003', rule_name='No verification step',
                        severity=RuleSeverity.ERROR,
                        message=f'Scenario "{scenario_name}" has no Then steps',
                        suggestion='Add assertions with Then/And steps',
                        category='workflow'
                    ))
                
                in_scenario = True
                has_then = False
                scenario_line = i
                scenario_name = re.sub(r'^Scenario.*?:\s*', '', line.strip())
            elif in_scenario and line.strip().startswith(('Feature', 'Background')):
                if not has_then:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W003', rule_name='No verification step',
                        severity=RuleSeverity.ERROR,
                        message=f'Scenario "{scenario_name}" has no Then steps',
                        category='workflow'
                    ))
                in_scenario = False
            
            if in_scenario and line.strip().startswith('Then'):
                has_then = True
        
        # W004: No action step (When required)
        in_scenario = False
        has_when = False
        scenario_line = 0
        scenario_name = ""
        for i, line in enumerate(parser.lines, 1):
            if line.strip().startswith('Scenario'):
                if in_scenario and not has_when:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W004', rule_name='No action step',
                        severity=RuleSeverity.ERROR,
                        message=f'Scenario "{scenario_name}" has no When steps',
                        suggestion='Add actions with When steps',
                        category='workflow'
                    ))
                
                in_scenario = True
                has_when = False
                scenario_line = i
                scenario_name = re.sub(r'^Scenario.*?:\s*', '', line.strip())
            elif in_scenario and line.strip().startswith(('Feature', 'Background')):
                if not has_when:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W004', rule_name='No action step',
                        severity=RuleSeverity.ERROR,
                        message=f'Scenario "{scenario_name}" has no When steps',
                        category='workflow'
                    ))
                in_scenario = False
            
            if in_scenario and line.strip().startswith('When'):
                has_when = True
        
        # W005: Step with period
        for i, line in enumerate(parser.lines, 1):
            if any(line.strip().startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                if line.strip().endswith('.'):
                    violations.append(Violation(
                        line=i, column=len(line.rstrip()),
                        rule_id='W005', rule_name='Step with period',
                        severity=RuleSeverity.INFO,
                        message='Step ends with a period',
                        suggestion='Remove trailing period',
                        category='workflow'
                    ))
        
        # W006: Too many steps
        in_scenario = False
        step_count = 0
        scenario_line = 0
        scenario_name = ""
        for i, line in enumerate(parser.lines, 1):
            if line.strip().startswith('Scenario'):
                if in_scenario and step_count > 10:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W006', rule_name='Too many steps',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario "{scenario_name}" has {step_count} steps',
                        suggestion='Break into simpler scenarios',
                        category='workflow'
                    ))
                
                in_scenario = True
                step_count = 0
                scenario_line = i
                scenario_name = re.sub(r'^Scenario.*?:\s*', '', line.strip())
            elif in_scenario and line.strip().startswith(('Feature', 'Background')):
                if step_count > 10:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W006', rule_name='Too many steps',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario "{scenario_name}" has {step_count} steps',
                        category='workflow'
                    ))
                in_scenario = False
            
            if in_scenario and any(line.strip().startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                step_count += 1
        
        return violations


class QualityRules:
    """FeatureMate-based quality checks"""
    
    @staticmethod
    def check_all(parser: UnifiedParser) -> List[Violation]:
        violations = []
        
        # Q001: Implementation details
        impl_keywords = [
            'clicks', 'selects', 'types', 'scrolls', 'presses', 'fills', 'enters', 
            'waits', 'refreshes', 'clears', 'hovering', 'clicking', 'navigates to',
            'button', 'link', 'input field', 'checkbox', 'page loads', 'refreshes page'
        ]
        
        for i, line in enumerate(parser.lines, 1):
            if any(line.strip().startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                for impl in impl_keywords:
                    if impl.lower() in line.lower():
                        violations.append(Violation(
                            line=i, column=1,
                            rule_id='Q001', rule_name='Implementation detail',
                            severity=RuleSeverity.WARNING,
                            message=f'Implementation detail: "{impl}"',
                            suggestion='Use business language instead of UI actions',
                            category='quality'
                        ))
                        break
        
        # SY001: Spell check (simplified - skip complex API usage)
        try:
            from spellchecker import SpellChecker
            spell = SpellChecker()
            
            # BDD keywords to skip from spell check
            bdd_keywords = {
                'feature', 'scenario', 'given', 'when', 'then', 'and', 'but', 'outline',
                'background', 'examples', 'gherkin', 'bdd', 'cucumber', 'pytest', 'behave',
                'automation', 'qa', 'tester', 'login', 'logout', 'password', 'username',
                'api', 'database', 'endpoint', 'payload', 'response', 'request',
                'selenium', 'webdriver', 'application', 'authentication',
            }
            
            for i, line in enumerate(parser.lines, 1):
                stripped = line.strip()
                # Check feature, scenario, and step lines
                if any(stripped.startswith(kw) for kw in ['Feature:', 'Scenario:', 'Given', 'When', 'Then', 'And', 'But']):
                    # Extract text (remove gherkin keywords)
                    text = re.sub(r'^(Feature:|Scenario:|Scenario Outline:|Given|When|Then|And|But|Background:)\s*', '', stripped, flags=re.IGNORECASE)
                    
                    # Split by spaces and special chars
                    words = re.findall(r'\b[a-zA-Z]+(?:_[a-zA-Z]+)?\b', text)
                    misspelled = spell.unknown(words)
                    
                    for word in misspelled:
                        # Skip if it's a BDD keyword or too short
                        if len(word) > 2 and word.lower() not in bdd_keywords and not word.isdigit():
                            suggestions = spell.correction(word)
                            col = line.find(word)
                            if col >= 0 and suggestions != word:
                                violations.append(Violation(
                                    line=i, column=col,
                                    rule_id='SY001', rule_name='Spelling error',
                                    severity=RuleSeverity.INFO,
                                    message=f'Possible spelling error: "{word}"',
                                    suggestion=f'Did you mean "{suggestions}"?',
                                    category='quality'
                                ))
        except Exception as e:
            # Skip spell check on any error
            pass
        
        return violations


class UnifiedLinter:
    """Main linter orchestrator"""
    
    def lint_file(self, file_path: str) -> List[Violation]:
        """Lint a single feature file"""
        parser = UnifiedParser().parse(file_path)
        
        violations = []
        violations.extend(StyleRules.check_all(parser))
        violations.extend(StructureRules.check_all(parser))
        violations.extend(WorkflowRules.check_all(parser))
        violations.extend(QualityRules.check_all(parser))
        
        # Sort by line number
        violations.sort(key=lambda v: (v.line, v.column))
        
        return violations
    
    def lint_directory(self, directory: str) -> dict:
        """Lint all feature files in directory"""
        path = Path(directory)
        results = {}
        
        for feature_file in sorted(path.rglob('*.feature')):
            violations = self.lint_file(str(feature_file))
            results[str(feature_file)] = violations
        
        return results
    
    def format_violations(self, violations: List[Violation], fmt='text') -> str:
        """Format violations"""
        if fmt == 'json':
            import json
            return json.dumps([{
                'line': v.line,
                'column': v.column,
                'rule': v.rule_id,
                'name': v.rule_name,
                'severity': v.severity.value,
                'message': v.message,
                'suggestion': v.suggestion,
                'category': v.category,
            } for v in violations], indent=2)
        else:
            lines = []
            for v in violations:
                lines.append(f"[{v.severity.name:7}] {v.rule_id}: {v.rule_name}")
                lines.append(f"  L{v.line}: {v.message}")
                if v.suggestion:
                    lines.append(f"  → {v.suggestion}")
            return '\n'.join(lines)


if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Unified BDD Linter - Combines gherkin-lint, cuke_linter, and quality checks',
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
    
    # Output
    total_violations = sum(len(v) for v in results.values())
    total_errors = sum(len([x for x in v if x.severity == RuleSeverity.ERROR]) 
                       for v in results.values())
    
    if args.format == 'json':
        output = {
            'summary': {
                'total_violations': total_violations,
                'total_errors': total_errors,
            },
            'files': {}
        }
        for file_path, violations in results.items():
            output['files'][file_path] = [v.__dict__ for v in violations]
        import json
        print(json.dumps(output, indent=2, default=str))
    else:
        # Text output
        if args.summary:
            print(f"Total violations: {total_violations}")
            print(f"Total errors: {total_errors}")
        else:
            for file_path, violations in results.items():
                if violations:
                    print(f"\n{file_path}")
                    print("=" * 80)
                    print(linter.format_violations(violations, 'text'))
                else:
                    print(f"✓ {file_path}")
            
            if results:
                print("\n" + "=" * 80)
                print(f"Summary: {total_violations} violation(s), {total_errors} error(s)")
    
    # Exit with error code if there are errors
    sys.exit(1 if total_errors > 0 else 0)
