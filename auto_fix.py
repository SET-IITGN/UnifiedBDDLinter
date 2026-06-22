#!/usr/bin/env python3
"""
Unified BDD Linter - Auto-fix Tool
Automatically corrects formatting and some structural issues
Includes context-aware fixes for structural violations
"""

import sys
import argparse
from pathlib import Path
import re


class AutoFixer:
    """Automatically fixes common linting violations with context awareness"""
    
    def __init__(self):
        self.changes_made = 0
        self.files_fixed = 0
        self.gherkin_keywords = {'Feature:', 'Scenario:', 'Given', 'When', 'Then', 'And', 'But', 'Background:'}
        self.ui_keywords = {
            'click': 'interact with',
            'clicks': 'interact with',
            'clicking': 'interacting with',
            'clicked': 'interacted with',
            'button': 'element',
            'input': 'field',
            'text': 'content',
            'page': 'application',
            'screen': 'application',
            'link': 'navigation element',
            'field': 'input',
            'form': 'data entry',
            'submit': 'confirm',
            'type': 'enter',
            'types': 'enter',
            'typing': 'entering',
            'typed': 'entered',
            'enters': 'provide',
            'clear': 'reset',
            'clears': 'reset',
            'clearing': 'resetting',
            'cleared': 'reset',
            'scroll': 'navigate to',
            'hover': 'position over',
            'drag': 'move',
            'drop': 'place'
        }
    
    def fix_file(self, file_path: str, dry_run: bool = False, output_dir: str = None) -> str:
        """
        Fix a single feature file with context-aware fixes
        Returns the final file path (may be different if file was renamed)
        
        Args:
            file_path: Path to the feature file to fix
            dry_run: If True, don't write changes
            output_dir: Optional directory to save fixed file to
        """
        original_file_path = file_path
        with open(file_path, 'r') as f:
            original_content = f.read()
        
        fixed_content = original_content
        
        # Fix 1: Fix feature name mismatch by RENAMING the file (ST007)
        # If output_dir is specified, don't rename (just save to output dir with kebab-case name)
        if output_dir:
            new_file_path = self._get_output_file_path(file_path, fixed_content, output_dir)
        else:
            new_file_path = self._fix_st007_via_file_rename(file_path, fixed_content, dry_run)
        
        # Fix 2: Ensure file structure is valid (Feature exists)
        fixed_content = self._ensure_feature_exists(fixed_content)
        
        # Fix 3: Add missing feature names
        fixed_content = self._fix_unnamed_feature(fixed_content)
        
        # Fix 4: Add missing scenario names
        fixed_content = self._fix_unnamed_scenarios(fixed_content)
        
        # Fix 5: Fix duplicate scenario names (ST006)
        fixed_content = self._fix_duplicate_scenarios(fixed_content)
        
        # Fix 6: Fix indentation (context-aware for Gherkin)
        fixed_content = self._fix_gherkin_indentation(fixed_content)
        
        # Fix 7: Add missing Then/When steps — DISABLED (not form-preserving).
        # Injecting placeholder "When action is performed" / "Then result is as
        # expected" changes scenario semantics and mis-orders steps, introducing
        # W002 (Given/When after Then) regressions. W003/W004 are now detect-only.
        # fixed_content = self._add_missing_verification_steps(fixed_content)

        # Fix 8: Replace implementation details — DISABLED (not form-preserving).
        # Rewriting step wording (e.g. "page"->"application") alters the meaning
        # of the test. Q001 is now detect-only.
        # fixed_content = self._fix_implementation_details(fixed_content)

        # Fix 9: Remove trailing whitespace
        fixed_content = self._fix_trailing_spaces(fixed_content)
        
        # Fix 10: Remove multiple empty lines
        fixed_content = self._fix_multiple_empty_lines(fixed_content)
        
        # Fix 11: Ensure file ends with newline
        fixed_content = self._fix_eof_newline(fixed_content)
        
        # Fix 12: Remove periods at end of steps
        fixed_content = self._fix_step_periods(fixed_content)
        
        # Fix 13: Fix spelling errors (SY001) — DISABLED (corrupts content).
        # The spell-checker rewrites legitimate technical terms into nonsense
        # ("sql"->"sol", "xml"->"my", "dble"->"able"). SY001 is now detect-only.
        # fixed_content = self._fix_spelling_errors(fixed_content)
        
        # Check if content changes were made
        if fixed_content != original_content:
            if not dry_run:
                with open(new_file_path, 'w') as f:
                    f.write(fixed_content)
                # NEVER delete/rename the original — output always goes to output_dir
                print(f"✓ Fixed  : {original_file_path}  →  {new_file_path}")
                self.files_fixed += 1
            else:
                print(f"[DRY RUN] Would fix: {original_file_path}  →  {new_file_path}")
            
            self._show_diff(original_content, fixed_content)
            return new_file_path
        else:
            # No fixes needed — still copy unchanged file to output_dir so the folder is complete
            if output_dir and not dry_run:
                with open(new_file_path, 'w') as f:
                    f.write(fixed_content)
            print(f"✓ Clean  : {original_file_path}  (no changes needed)")
            return new_file_path
    
    def fix_directory(self, directory: str, dry_run: bool = False, output_dir: str = None):
        """Fix all feature files in a directory"""
        path = Path(directory)
        feature_files = sorted(path.rglob('*.feature'))
        
        if not feature_files:
            print(f"No feature files found in {directory}")
            return
        
        print(f"Found {len(feature_files)} feature file(s)\n")
        
        renamed_files = 0
        for feature_file in feature_files:
            new_file_path = self.fix_file(str(feature_file), dry_run, output_dir)
            if str(feature_file) != new_file_path:
                renamed_files += 1
        
        print(f"\n{'='*80}")
        print(f"Summary: {self.files_fixed} file(s) fixed, {renamed_files} file(s) renamed")
    
    def _get_output_file_path(self, input_file_path: str, content: str, output_dir: str) -> str:
        """
        Get the output file path when using --output option
        Generates kebab-case filename based on Feature: name
        """
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Extract Feature: name to generate output filename
        feature_name = AutoFixer._extract_feature_name(content)
        
        if feature_name and feature_name.strip().lower() not in ['', 'feature', 'auto-generated feature', 'new feature']:
            # Use Feature: name for output filename (kebab-case)
            desired_file_name = feature_name.lower().replace(' ', '-').replace('_', '-')
            desired_file_name = re.sub(r'[^a-z0-9-]', '', desired_file_name)
            desired_file_name = re.sub(r'-+', '-', desired_file_name).strip('-')
        else:
            # Fall back to original filename
            desired_file_name = Path(input_file_path).stem
        
        output_file_path = output_path / f"{desired_file_name}.feature"

        # Collision guard: if target already exists, append original stem to disambiguate
        if output_file_path.exists():
            original_stem = Path(input_file_path).stem
            output_file_path = output_path / f"{desired_file_name}--{original_stem}.feature"
            print(f"  ⚠ Name collision: saved as {output_file_path.name} (original: {Path(input_file_path).name})")

        return str(output_file_path)
    
    def _fix_st007_via_file_rename(self, file_path: str, content: str, dry_run: bool = False) -> str:
        """
        Fix ST007 (Feature name must match file name) by RENAMING the file to match the Feature: description
        This preserves the semantic meaning that users wrote in the Feature: line
        Returns the new file path
        
        Naming Convention: kebab-case (gherkin-lint style)
        - Supports both snake_case (cuke_linter) and kebab-case (gherkin-lint)
        - Auto-fix generates kebab-case for consistency with gherkin-lint
        
        INFO: If Feature: is empty or auto-generated, no rename is performed (user should provide meaningful name)
        """
        from pathlib import Path
        
        # Extract current file name without extension
        current_file_path = Path(file_path)
        current_file_name = current_file_path.stem
        
        # Extract Feature: name from content
        feature_name = self._extract_feature_name(content)
        
        # ✅ KEY INSIGHT: Only rename if Feature has a meaningful, user-provided description
        # Skip renaming if Feature is empty or auto-generated (user should fix this first)
        if not feature_name or feature_name.strip().lower() in ['', 'feature', 'auto-generated feature', 'new feature']:
            # Preserve original file name - requires user to add meaningful feature description
            return file_path
        
        # Convert Feature name to kebab-case filename (spaces/underscores→hyphens, lowercase)
        # Follows gherkin-lint convention
        desired_file_name = feature_name.lower().replace(' ', '-').replace('_', '-')
        # Remove any special characters that aren't alphanumeric or hyphens
        desired_file_name = re.sub(r'[^a-z0-9-]', '', desired_file_name)
        
        # Normalize file name (remove extra hyphens)
        desired_file_name = re.sub(r'-+', '-', desired_file_name).strip('-')
        
        # Add .feature extension
        desired_full_name = f"{desired_file_name}.feature"
        new_file_path = current_file_path.parent / desired_full_name
        
        # Check if rename is needed (normalize both for comparison - support both snake_case and kebab-case)
        current_normalized = current_file_name.lower().replace('_', '-').replace('-', '-')
        desired_normalized = desired_file_name.lower()
        
        if current_normalized == desired_normalized:
            # File name already matches feature name (after normalization)
            return file_path
        
        # Check for existing file with same name (collision)
        if new_file_path.exists() and new_file_path != current_file_path:
            print(f"⚠ Warning: Target file {desired_full_name} already exists. Keeping original {current_file_path.name}")
            return file_path
        
        # Perform the rename
        if not dry_run:
            try:
                current_file_path.rename(new_file_path)
                print(f"  📁 Renamed: {current_file_path.name} → {desired_full_name}")
                print(f"    (Feature: '{feature_name}' now matches filename in kebab-case)")
                return str(new_file_path)
            except OSError as e:
                print(f"⚠ Failed to rename {current_file_path.name} to {desired_full_name}: {e}")
                return file_path
        else:
            print(f"  [DRY RUN] Would rename: {current_file_path.name} → {desired_full_name}")
            return str(new_file_path)
    
    @staticmethod
    def _extract_feature_name(content: str) -> str:
        """Extract the Feature: name from content"""
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('Feature:'):
                # Extract name after "Feature:" keyword
                feature_name = line.strip()[8:].strip()  # Remove "Feature:" prefix and whitespace
                return feature_name
        return ""
    
    @staticmethod
    def _ensure_feature_exists(content: str) -> str:
        """Ensure file has a Feature block"""
        if not content.strip():
            return 'Feature: New Feature\n\n  Scenario: New Scenario\n    Given initial condition\n    When action occurs\n    Then result is visible\n'
        
        if not re.search(r'\bFeature:', content, re.MULTILINE):
            # Add Feature block at the beginning
            content = 'Feature: Auto-generated Feature\n\n' + content
        
        return content
    
    @staticmethod
    def _fix_unnamed_feature(content: str) -> str:
        """Add name to unnamed Feature blocks"""
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            if line.strip() == 'Feature:':
                fixed_lines.append('Feature: Auto-generated Feature')
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_unnamed_scenarios(content: str) -> str:
        """Add name to unnamed Scenario blocks"""
        lines = content.split('\n')
        fixed_lines = []
        scenario_counter = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == 'Scenario:':
                scenario_counter += 1
                indent = line[:len(line) - len(stripped)]
                fixed_lines.append(f'{indent}Scenario: Scenario {scenario_counter}')
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_duplicate_scenarios(content: str) -> str:
        """Fix duplicate scenario names by appending numeric suffixes (ST006)"""
        lines = content.split('\n')
        fixed_lines = []
        scenario_names = {}  # Track scenario name occurrences: {name: count}
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith('Scenario:') or stripped.startswith('Scenario Outline:'):
                # Extract indentation and keyword
                indent = line[:len(line) - len(stripped)]
                if stripped.startswith('Scenario Outline:'):
                    keyword = 'Scenario Outline:'
                    scenario_name = stripped[17:].strip()  # After "Scenario Outline:"
                else:
                    keyword = 'Scenario:'
                    scenario_name = stripped[9:].strip()  # After "Scenario:"
                
                # Skip if no name
                if not scenario_name or scenario_name.lower() in ['scenario', 'outline']:
                    fixed_lines.append(line)
                    continue
                
                # Check if this scenario name has been seen before
                if scenario_name in scenario_names:
                    scenario_names[scenario_name] += 1
                    # Append a numeric suffix to make it unique
                    new_name = f"{scenario_name} {scenario_names[scenario_name]}"
                    fixed_lines.append(f'{indent}{keyword} {new_name}')
                else:
                    scenario_names[scenario_name] = 1
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_gherkin_indentation(content: str) -> str:
        """Fix indentation with context awareness for Gherkin keywords"""
        lines = content.split('\n')
        fixed_lines = []
        
        feature_found = False
        in_scenario = False
        in_examples = False
        
        for line in lines:
            if not line.strip():  # Empty line
                fixed_lines.append('')
                continue
            
            stripped = line.strip()
            
            # Check keyword type
            is_feature = stripped.startswith('Feature:')
            is_background = stripped.startswith('Background:')
            is_scenario = stripped.startswith('Scenario:') or stripped.startswith('Scenario Outline:')
            is_step = any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But'])
            is_examples = stripped.startswith('Examples:')
            is_table_row = stripped.startswith('|')
            
            # Determine correct indentation
            # All Gherkin keywords (Feature, Scenario, Examples, etc.) start at column 0
            # Steps get 2-space indent
            # Table rows get 2-space indent
            if is_feature or is_background or is_scenario or is_examples:
                new_indent = ''  # All keywords at column 0
                if is_scenario:
                    in_scenario = True
                if is_examples:
                    in_examples = True
            elif is_step:
                new_indent = '  '  # 2-space indent for steps
            elif is_table_row:
                new_indent = '  '  # 2-space indent for table rows
            else:
                # Other content - don't indent
                new_indent = ''
            
            fixed_lines.append(new_indent + stripped)
        
        return '\n'.join(fixed_lines)
    
    def _add_missing_verification_steps(self, content: str) -> str:
        """Add Then steps if missing, add When steps if missing"""
        lines = content.split('\n')
        fixed_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check if this is a scenario start
            if stripped.startswith('Scenario:'):
                fixed_lines.append(line)
                indent = line[:len(line) - len(stripped)]
                
                # Look ahead to find step types
                has_when = False
                has_then = False
                step_indent = indent + '  '
                
                j = i + 1
                while j < len(lines) and lines[j].strip():
                    if not any(lines[j].strip().startswith(kw) for kw in ['Scenario:', 'Feature:', 'Background:']):
                        step_line = lines[j].strip()
                        if step_line.startswith('When'):
                            has_when = True
                        elif step_line.startswith('Then'):
                            has_then = True
                    j += 1
                
                # Collect scenario steps
                j = i + 1
                scenario_steps = []
                while j < len(lines) and lines[j].strip():
                    if any(lines[j].strip().startswith(kw) for kw in ['Scenario:', 'Feature:', 'Background:']):
                        break
                    scenario_steps.append(lines[j])
                    j += 1
                
                # Add collected steps
                for step in scenario_steps:
                    fixed_lines.append(step)
                
                # Add missing steps
                if not has_then and scenario_steps:
                    fixed_lines.append(f'{step_indent}Then result is as expected')
                
                if not has_when and scenario_steps:
                    # Insert When if we have Given but no When
                    has_given = any('Given' in s for s in scenario_steps)
                    if has_given:
                        # Insert before the first Then or at end
                        insert_idx = len(fixed_lines)
                        for idx in range(len(fixed_lines) - 1, -1, -1):
                            if 'Then' in fixed_lines[idx]:
                                insert_idx = idx
                                break
                        fixed_lines.insert(insert_idx, f'{step_indent}When action is performed')
                
                i = j
                continue
            
            fixed_lines.append(line)
            i += 1
        
        return '\n'.join(fixed_lines)
    
    def _fix_implementation_details(self, content: str) -> str:
        """Replace UI implementation details with business language"""
        lines = content.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Only fix step lines
            if any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                fixed_line = line
                # Replace UI keywords with business language
                for ui_term, business_term in self.ui_keywords.items():
                    # Case-insensitive replacement
                    pattern = re.compile(r'\b' + ui_term + r'\b', re.IGNORECASE)
                    fixed_line = pattern.sub(business_term, fixed_line)
                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_trailing_spaces(content: str) -> str:
        """Remove trailing whitespace from each line"""
        lines = content.split('\n')
        fixed_lines = [line.rstrip() for line in lines]
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_multiple_empty_lines(content: str) -> str:
        """Replace multiple consecutive empty lines with single empty line"""
        # Replace 3+ empty lines with 2 (one empty line)
        content = re.sub(r'\n\n\n+', '\n\n', content)
        return content
    
    @staticmethod
    def _fix_eof_newline(content: str) -> str:
        """Ensure file ends with newline"""
        if content and not content.endswith('\n'):
            content += '\n'
        return content
    
    @staticmethod
    def _fix_step_periods(content: str) -> str:
        """Remove periods at end of steps"""
        lines = content.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in ['Given', 'When', 'Then', 'And', 'But']):
                if stripped.endswith('.'):
                    # Remove period
                    indent = line[:len(line) - len(stripped)]
                    fixed_lines.append(indent + stripped[:-1])
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_spelling_errors(content: str) -> str:
        """Fix spelling errors (SY001 auto-fix)"""
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
            
            lines = content.split('\n')
            fixed_lines = []
            
            for line in lines:
                stripped = line.strip()
                
                # Check feature, scenario, and step lines
                if any(stripped.startswith(kw) for kw in ['Feature:', 'Scenario:', 'Given', 'When', 'Then', 'And', 'But']):
                    # Extract text (remove gherkin keywords)
                    text = re.sub(r'^(Feature:|Scenario:|Scenario Outline:|Given|When|Then|And|But|Background:)\s*', '', stripped, flags=re.IGNORECASE)
                    
                    # Find and fix misspelled words
                    words = re.findall(r'\b[a-zA-Z]+(?:_[a-zA-Z]+)?\b', text)
                    misspelled = spell.unknown(words)
                    
                    fixed_line = line
                    for word in misspelled:
                        if len(word) > 2 and word.lower() not in bdd_keywords and not word.isupper():  # Skip short words, BDD terms, and acronyms
                            suggestion = spell.correction(word)
                            if suggestion and suggestion != word:
                                # Replace the word
                                fixed_line = re.sub(r'\b' + re.escape(word) + r'\b', suggestion, fixed_line, flags=re.IGNORECASE)
                    
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            
            return '\n'.join(fixed_lines)
        except Exception:
            # If spell check fails, return unchanged
            return content
    
    @staticmethod
    def _show_diff(original: str, fixed: str):
        """Show what changed (brief summary)"""
        original_lines = original.split('\n')
        fixed_lines = fixed.split('\n')
        
        changes = []
        for i, (orig, fix) in enumerate(zip(original_lines, fixed_lines), 1):
            if orig != fix:
                changes.append(f"  L{i}: Changed")
        
        if changes:
            print(f"  Changes: {len(changes)} line(s) modified")
            for change in changes[:3]:  # Show first 3
                print(f"    {change}")
            if len(changes) > 3:
                print(f"    ... and {len(changes) - 3} more")
            print()


def main():
    parser = argparse.ArgumentParser(
        description='Unified BDD Linter - Auto-fix Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python auto_fix.py my_feature.feature
  python auto_fix.py features/ --dry-run
  python auto_fix.py features/
  python auto_fix.py my_feature.feature --output fixed/
  python auto_fix.py features/ --output output_folder/
        '''
    )
    
    parser.add_argument('path', help='Feature file or directory to fix')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be fixed without making changes')
    parser.add_argument('--output', '-o', dest='output_dir', default='fixed_features',
                        help='Directory to save fixed files (default: fixed_features/). Originals are never modified.')
    parser.add_argument('--no-indentation', action='store_true',
                        help='Skip indentation fixes')
    parser.add_argument('--no-spacing', action='store_true',
                        help='Skip trailing space and empty line fixes')
    parser.add_argument('--no-periods', action='store_true',
                        help='Skip step period removal')
    
    args = parser.parse_args()
    
    path = Path(args.path)
    fixer = AutoFixer()

    # Resolve output dir relative to input path so originals are never touched
    if path.is_file():
        output_dir = args.output_dir if Path(args.output_dir).is_absolute() \
            else str(path.parent / args.output_dir)
    else:
        output_dir = args.output_dir if Path(args.output_dir).is_absolute() \
            else str(path.parent / args.output_dir)

    if not args.dry_run:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        print(f"Originals kept in : {path}")
        print(f"Fixed files saved to: {output_dir}")
        print()

    if path.is_file():
        fixer.fix_file(str(path), args.dry_run, output_dir)
    elif path.is_dir():
        fixer.fix_directory(str(path), args.dry_run, output_dir)
    else:
        print(f"Error: {args.path} not found")
        sys.exit(1)


if __name__ == '__main__':
    main()
