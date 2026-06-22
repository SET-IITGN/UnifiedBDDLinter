"""
Unified BDD Linter - Combines gherkin-lint, cuke_linter, and FeatureMate
Comprehensive validation for Gherkin feature files
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional
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
    category: str = ""  # style, workflow, quality, structure


class UnifiedParser:
    """Unified Gherkin parser supporting all validations"""
    
    KEYWORDS = {
        'Feature': r'^\s*Feature:',
        'Background': r'^\s*Background:',
        'Scenario': r'^\s*Scenario:',
        'Scenario Outline': r'^\s*Scenario Outline:',
        'Examples': r'^\s*Examples:',
        'Given': r'^\s*(Given|And|But)\s+',
        'When': r'^\s*(When|And|But)\s+',
        'Then': r'^\s*(Then|And|But)\s+',
        'Tag': r'^\s*@',
        'Comment': r'^\s*#',
    }
    
    def __init__(self):
        self.content = []
        self.file_path = ""
        self.lines = []
        
    def parse(self, file_path: str):
        """Parse a feature file"""
        self.file_path = file_path
        with open(file_path, 'r') as f:
            self.lines = f.readlines()
        return self
    
    def get_line(self, line_num: int) -> str:
        """Get line content (1-indexed)"""
        if 0 < line_num <= len(self.lines):
            return self.lines[line_num - 1].rstrip()
        return ""
    
    def get_indentation(self, line_num: int) -> int:
        """Get indentation level of a line"""
        line = self.get_line(line_num)
        return len(line) - len(line.lstrip())
    
    def is_empty_line(self, line_num: int) -> bool:
        """Check if line is empty or whitespace-only"""
        line = self.get_line(line_num)
        return not line.strip()


class StyleRules:
    """gherkin-lint style rules"""
    
    @staticmethod
    def check_trailing_spaces(parser: UnifiedParser) -> List[Violation]:
        """No trailing spaces"""
        violations = []
        for i, line in enumerate(parser.lines, 1):
            if line.rstrip() != line.rstrip('\n'):
                violations.append(Violation(
                    line=i, column=len(line.rstrip()) + 1,
                    rule_id='S001', rule_name='No trailing spaces',
                    severity=RuleSeverity.WARNING,
                    message=f'Line {i} has trailing whitespace',
                    category='style'
                ))
        return violations
    
    @staticmethod
    def check_multiple_empty_lines(parser: UnifiedParser) -> List[Violation]:
        """No multiple consecutive empty lines"""
        violations = []
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
        return violations
    
    @staticmethod
    def check_eof_newline(parser: UnifiedParser) -> List[Violation]:
        """File must end with newline"""
        violations = []
        if parser.lines and not parser.lines[-1].endswith('\n'):
            violations.append(Violation(
                line=len(parser.lines), column=1,
                rule_id='S003', rule_name='EOF newline',
                severity=RuleSeverity.INFO,
                message='File does not end with newline',
                suggestion='Add newline at end of file',
                category='style'
            ))
        return violations
    
    @staticmethod
    def check_indentation(parser: UnifiedParser) -> List[Violation]:
        """Check proper indentation"""
        violations = []
        expected_indent = {
            'Feature': 0,
            'Background': 0,
            'Scenario': 0,
            'When': 2,
            'Given': 2,
            'Then': 2,
            'And': 2,
            'But': 2,
            'Examples': 0,
        }
        
        for i, line in enumerate(parser.lines, 1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            for keyword, expected in expected_indent.items():
                if stripped.startswith(keyword + ':') or (keyword in ['When', 'Given', 'Then', 'And', 'But'] and 
                                                          re.match(f'^({keyword}|And|But)', stripped)):
                    if keyword in ['Given', 'When', 'Then', 'And', 'But']:
                        if indent != 2:
                            violations.append(Violation(
                                line=i, column=1,
                                rule_id='S004', rule_name='Indentation',
                                severity=RuleSeverity.ERROR,
                                message=f'Line {i}: Expected indent {expected}, got {indent}',
                                suggestion=f'Use {expected} spaces for indentation',
                                category='style'
                            ))
                    elif indent != expected:
                        violations.append(Violation(
                            line=i, column=1,
                            rule_id='S004', rule_name='Indentation',
                            severity=RuleSeverity.ERROR,
                            message=f'Line {i}: {keyword} should not be indented',
                            category='style'
                        ))
                    break
        
        return violations
    
    @staticmethod
    def check_file_name(file_path: str) -> List[Violation]:
        """File should be snake_case.feature or kebab-case.feature.

        The project supports both conventions (snake_case for cuke_linter,
        kebab-case for gherkin-lint), and auto_fix.py renames to kebab-case,
        so the hyphen must be accepted here too — otherwise S005 would flag
        the very filename auto_fix.py produces.
        """
        violations = []
        filename = Path(file_path).name
        if not re.match(r'^[a-z0-9_-]+\.feature$', filename):
            violations.append(Violation(
                line=1, column=1,
                rule_id='S005', rule_name='File name format',
                severity=RuleSeverity.ERROR,
                message=f'Invalid filename: {filename}',
                suggestion='Use kebab-case: my-feature.feature',
                category='style'
            ))
        return violations
    
    @staticmethod
    def check_name_length(parser: UnifiedParser, max_feature=80, max_scenario=80, max_step=100) -> List[Violation]:
        """Check name length limits"""
        violations = []
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('Feature:'):
                name = stripped.replace('Feature:', '').strip()
                if len(name) > max_feature:
                    violations.append(Violation(
                        line=i, column=len('Feature:') + 1,
                        rule_id='S006', rule_name='Name length',
                        severity=RuleSeverity.WARNING,
                        message=f'Feature name too long ({len(name)} > {max_feature})',
                        category='style'
                    ))
            
            elif stripped.startswith('Scenario'):
                name = re.sub(r'^Scenario(Outline)?:', '', stripped).strip()
                if len(name) > max_scenario:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='S006', rule_name='Name length',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario name too long ({len(name)} > {max_scenario})',
                        category='style'
                    ))
            
            elif any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                if len(stripped) > max_step:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='S006', rule_name='Name length',
                        severity=RuleSeverity.INFO,
                        message=f'Step too long ({len(stripped)} > {max_step})',
                        category='style'
                    ))
        
        return violations


class StructureRules:
    """Gherkin structural rules"""
    
    @staticmethod
    def check_unnamed_features(parser: UnifiedParser) -> List[Violation]:
        """Features must have names"""
        violations = []
        for i, line in enumerate(parser.lines, 1):
            if line.strip() == 'Feature:':
                violations.append(Violation(
                    line=i, column=1,
                    rule_id='ST001', rule_name='Unnamed feature',
                    severity=RuleSeverity.ERROR,
                    message='Feature must have a name',
                    category='structure'
                ))
        return violations
    
    @staticmethod
    def check_unnamed_scenarios(parser: UnifiedParser) -> List[Violation]:
        """Scenarios must have names"""
        violations = []
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            if stripped in ['Scenario:', 'Scenario Outline:']:
                violations.append(Violation(
                    line=i, column=1,
                    rule_id='ST002', rule_name='Unnamed scenario',
                    severity=RuleSeverity.ERROR,
                    message='Scenario must have a name',
                    category='structure'
                ))
        return violations
    
    @staticmethod
    def check_empty_file(parser: UnifiedParser) -> List[Violation]:
        """File cannot be empty"""
        violations = []
        if not any(line.strip() for line in parser.lines):
            violations.append(Violation(
                line=1, column=1,
                rule_id='ST003', rule_name='Empty file',
                severity=RuleSeverity.ERROR,
                message='File is empty',
                category='structure'
            ))
        return violations
    
    @staticmethod
    def check_no_feature(parser: UnifiedParser) -> List[Violation]:
        """File must have Feature"""
        violations = []
        has_feature = any(line.strip().startswith('Feature:') for line in parser.lines)
        if not has_feature:
            violations.append(Violation(
                line=1, column=1,
                rule_id='ST004', rule_name='No feature',
                severity=RuleSeverity.ERROR,
                message='File must contain a Feature',
                category='structure'
            ))
        return violations
    
    @staticmethod
    def check_empty_background(parser: UnifiedParser) -> List[Violation]:
        """Background must have steps"""
        violations = []
        for i, line in enumerate(parser.lines, 1):
            if line.strip() == 'Background:':
                # Check if next meaningful line is Scenario or Feature
                for j in range(i, len(parser.lines)):
                    next_line = parser.lines[j].strip()
                    if next_line and not next_line.startswith('#'):
                        if next_line.startswith(('Scenario', 'Feature')):
                            violations.append(Violation(
                                line=i, column=1,
                                rule_id='ST005', rule_name='Empty background',
                                severity=RuleSeverity.WARNING,
                                message='Background has no steps',
                                category='structure'
                            ))
                        break
        return violations
    
    @staticmethod
    def check_duplicate_scenario_names(parser: UnifiedParser) -> List[Violation]:
        """No duplicate scenario names"""
        violations = []
        scenario_names = {}
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            if stripped.startswith('Scenario'):
                name = re.sub(r'^Scenario(Outline)?:', '', stripped).strip()
                if name in scenario_names:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='ST006', rule_name='Duplicate scenario name',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario "{name}" is duplicated (line {scenario_names[name]})',
                        category='structure'
                    ))
                else:
                    scenario_names[name] = i
        return violations


class WorkflowRules:
    """cuke_linter workflow rules"""
    
    @staticmethod
    def check_only_one_when(parser: UnifiedParser) -> List[Violation]:
        """Scenario should have only one When"""
        violations = []
        in_scenario = False
        when_count = 0
        scenario_line = 0
        
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('Scenario'):
                in_scenario = True
                when_count = 0
                scenario_line = i
            elif in_scenario and stripped.startswith(('Scenario', 'Feature', 'Background')):
                in_scenario = False
            
            if in_scenario and stripped.startswith('When'):
                when_count += 1
                if when_count > 1:
                    violations.append(Violation(
                        line=i, column=1,
                        rule_id='W001', rule_name='Only one When',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario at line {scenario_line} has multiple When steps',
                        suggestion='Use And/But for additional actions',
                        category='workflow'
                    ))
        return violations
    
    @staticmethod
    def check_gwt_structure(parser: UnifiedParser) -> List[Violation]:
        """Steps must follow Given-When-Then order"""
        violations = []
        in_scenario = False
        last_keyword_type = None  # 'given', 'when', 'then'
        scenario_line = 0
        
        keyword_type_map = {
            'Given': 'given',
            'When': 'when',
            'Then': 'then',
            'And': None,  # Depends on context
            'But': None,
        }
        
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('Scenario'):
                in_scenario = True
                last_keyword_type = None
                scenario_line = i
            elif in_scenario and stripped.startswith(('Scenario', 'Feature', 'Background')):
                in_scenario = False
            
            if in_scenario:
                for keyword in ['Given', 'When', 'Then', 'And', 'But']:
                    if stripped.startswith(keyword):
                        current_type = keyword_type_map.get(keyword)
                        
                        if keyword in ['And', 'But']:
                            # And/But inherits previous type
                            pass
                        else:
                            # Check order
                            if last_keyword_type == 'then' and current_type in ['given', 'when']:
                                violations.append(Violation(
                                    line=i, column=1,
                                    rule_id='W002', rule_name='GWT order',
                                    severity=RuleSeverity.ERROR,
                                    message=f'{keyword} step after Then (wrong order)',
                                    suggestion='Follow Given-When-Then order',
                                    category='workflow'
                                ))
                            elif last_keyword_type == 'when' and current_type == 'given':
                                violations.append(Violation(
                                    line=i, column=1,
                                    rule_id='W002', rule_name='GWT order',
                                    severity=RuleSeverity.ERROR,
                                    message=f'Given step after When (wrong order)',
                                    category='workflow'
                                ))
                            
                            last_keyword_type = current_type
                        break
        
        return violations
    
    @staticmethod
    def check_no_verification_step(parser: UnifiedParser) -> List[Violation]:
        """Scenarios should have Then steps"""
        violations = []
        in_scenario = False
        has_then = False
        scenario_line = 0
        scenario_name = ""
        
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('Scenario'):
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
                scenario_name = re.sub(r'^Scenario.*?:\s*', '', stripped)
            
            elif in_scenario and stripped.startswith(('Feature', 'Background')):
                if not has_then:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W003', rule_name='No verification step',
                        severity=RuleSeverity.ERROR,
                        message=f'Scenario "{scenario_name}" has no Then steps',
                        category='workflow'
                    ))
                in_scenario = False
            
            if in_scenario and stripped.startswith('Then'):
                has_then = True
        
        return violations
    
    @staticmethod
    def check_no_action_step(parser: UnifiedParser) -> List[Violation]:
        """Scenarios should have When steps"""
        violations = []
        in_scenario = False
        has_when = False
        scenario_line = 0
        scenario_name = ""
        
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('Scenario'):
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
                scenario_name = re.sub(r'^Scenario.*?:\s*', '', stripped)
            
            elif in_scenario and stripped.startswith(('Feature', 'Background')):
                if not has_when:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W004', rule_name='No action step',
                        severity=RuleSeverity.ERROR,
                        message=f'Scenario "{scenario_name}" has no When steps',
                        category='workflow'
                    ))
                in_scenario = False
            
            if in_scenario and stripped.startswith('When'):
                has_when = True
        
        return violations
    
    @staticmethod
    def check_step_with_period(parser: UnifiedParser) -> List[Violation]:
        """Steps should not end with period"""
        violations = []
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                if stripped.endswith('.'):
                    violations.append(Violation(
                        line=i, column=len(stripped),
                        rule_id='W005', rule_name='Step with period',
                        severity=RuleSeverity.INFO,
                        message='Step ends with a period',
                        suggestion='Remove trailing period',
                        category='workflow'
                    ))
        return violations
    
    @staticmethod
    def check_too_many_steps(parser: UnifiedParser, max_steps=10) -> List[Violation]:
        """Scenarios should not have too many steps"""
        violations = []
        in_scenario = False
        step_count = 0
        scenario_line = 0
        scenario_name = ""
        
        for i, line in enumerate(parser.lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('Scenario'):
                if in_scenario and step_count > max_steps:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W006', rule_name='Too many steps',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario "{scenario_name}" has {step_count} steps (> {max_steps})',
                        suggestion='Break complex scenarios into simpler ones',
                        category='workflow'
                    ))
                
                in_scenario = True
                step_count = 0
                scenario_line = i
                scenario_name = re.sub(r'^Scenario.*?:\s*', '', stripped)
            
            elif in_scenario and stripped.startswith(('Feature', 'Background', 'Scenario Outline')):
                if step_count > max_steps:
                    violations.append(Violation(
                        line=scenario_line, column=1,
                        rule_id='W006', rule_name='Too many steps',
                        severity=RuleSeverity.WARNING,
                        message=f'Scenario "{scenario_name}" has {step_count} steps (> {max_steps})',
                        category='workflow'
                    ))
                in_scenario = False
            
            if in_scenario and any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                step_count += 1
        
        return violations


class UnifiedLinter:
    """Main linter combining all rules"""
    
    def __init__(self):
        self.violations: List[Violation] = []
        self.file_count = 0
        self.total_violations = 0
    
    def lint_file(self, file_path: str) -> List[Violation]:
        """Lint a single feature file"""
        parser = UnifiedParser().parse(file_path)
        violations = []
        
        # Style rules
        violations.extend(StyleRules.check_trailing_spaces(parser))
        violations.extend(StyleRules.check_multiple_empty_lines(parser))
        violations.extend(StyleRules.check_eof_newline(parser))
        violations.extend(StyleRules.check_indentation(parser))
        violations.extend(StyleRules.check_file_name(file_path))
        violations.extend(StyleRules.check_name_length(parser))
        
        # Structure rules
        violations.extend(StructureRules.check_unnamed_features(parser))
        violations.extend(StructureRules.check_unnamed_scenarios(parser))
        violations.extend(StructureRules.check_empty_file(parser))
        violations.extend(StructureRules.check_no_feature(parser))
        violations.extend(StructureRules.check_empty_background(parser))
        violations.extend(StructureRules.check_duplicate_scenario_names(parser))
        
        # Workflow rules
        violations.extend(WorkflowRules.check_only_one_when(parser))
        violations.extend(WorkflowRules.check_gwt_structure(parser))
        violations.extend(WorkflowRules.check_no_verification_step(parser))
        violations.extend(WorkflowRules.check_no_action_step(parser))
        violations.extend(WorkflowRules.check_step_with_period(parser))
        violations.extend(WorkflowRules.check_too_many_steps(parser))
        
        # Sort by line number
        violations.sort(key=lambda v: (v.line, v.column))
        
        self.total_violations += len(violations)
        self.file_count += 1
        
        return violations
    
    def lint_directory(self, directory: str) -> dict:
        """Lint all feature files in directory"""
        path = Path(directory)
        results = {}
        
        for feature_file in sorted(path.rglob('*.feature')):
            violations = self.lint_file(str(feature_file))
            results[str(feature_file)] = violations
        
        return results
    
    def format_output(self, violations: List[Violation], format_type='text') -> str:
        """Format violations for output"""
        if format_type == 'json':
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
        
        else:  # text
            output = []
            for v in violations:
                output.append(f"[{v.severity.name:7}] {v.rule_id}: {v.rule_name}")
                output.append(f"  Line {v.line}: {v.message}")
                if v.suggestion:
                    output.append(f"  Suggestion: {v.suggestion}")
            return '\n'.join(output)
