#!/usr/bin/env python3
"""Fix Black formatting issues in Python files."""

import os
import re
from pathlib import Path

def apply_black_formatting(content):
    """Apply Black formatting rules to Python code."""
    lines = content.split('\n')
    formatted_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        original_line = line
        
        # Remove trailing whitespace
        line = line.rstrip()
        
        # Fix long lines by breaking them appropriately
        if len(line) > 88 and not line.strip().startswith('#'):
            # Handle function calls with multiple arguments
            if '(' in line and ')' in line and ',' in line:
                indent = len(line) - len(line.lstrip())
                if line.strip().endswith(')'):
                    # Split function call
                    func_part = line[:line.find('(') + 1]
                    args_part = line[line.find('(') + 1:line.rfind(')')]
                    end_part = line[line.rfind(')'):]
                    
                    if ',' in args_part:
                        args = [arg.strip() for arg in args_part.split(',')]
                        formatted_lines.append(func_part)
                        for j, arg in enumerate(args):
                            if j == len(args) - 1:
                                formatted_lines.append(' ' * (indent + 4) + arg + ',')
                            else:
                                formatted_lines.append(' ' * (indent + 4) + arg + ',')
                        formatted_lines.append(' ' * indent + end_part)
                        i += 1
                        continue
            
            # Handle logger calls
            if 'logger.' in line and '(' in line:
                indent = len(line) - len(line.lstrip())
                if ',' in line:
                    parts = line.split('(', 1)
                    if len(parts) == 2:
                        func_part = parts[0] + '('
                        rest = parts[1]
                        if rest.endswith(')'):
                            args_part = rest[:-1]
                            formatted_lines.append(func_part)
                            # Split arguments
                            args = []
                            current_arg = ""
                            paren_count = 0
                            quote_char = None
                            
                            for char in args_part:
                                if char in ['"', "'"] and quote_char is None:
                                    quote_char = char
                                elif char == quote_char:
                                    quote_char = None
                                elif char == '(' and quote_char is None:
                                    paren_count += 1
                                elif char == ')' and quote_char is None:
                                    paren_count -= 1
                                elif char == ',' and paren_count == 0 and quote_char is None:
                                    args.append(current_arg.strip())
                                    current_arg = ""
                                    continue
                                current_arg += char
                            
                            if current_arg.strip():
                                args.append(current_arg.strip())
                            
                            for arg in args:
                                formatted_lines.append(' ' * (indent + 4) + arg + ',')
                            formatted_lines.append(' ' * indent + ')')
                            i += 1
                            continue
        
        # Fix import statements
        if line.strip().startswith('from') and '(' in line and ')' not in line:
            # Multi-line import
            import_lines = [line]
            i += 1
            while i < len(lines) and ')' not in lines[i]:
                import_lines.append(lines[i])
                i += 1
            if i < len(lines):
                import_lines.append(lines[i])
            
            # Reformat the import
            if len(import_lines) > 1:
                base_import = import_lines[0]
                imports = []
                for imp_line in import_lines[1:]:
                    if ')' in imp_line:
                        imp_line = imp_line.replace(')', '').strip()
                    if imp_line.strip():
                        clean_import = imp_line.strip().rstrip(',')
                        if clean_import:
                            imports.append(clean_import)
                
                formatted_lines.append(base_import)
                for j, imp in enumerate(imports):
                    formatted_lines.append('    ' + imp + ',')
                formatted_lines.append(')')
                i += 1
                continue
        
        # Add proper spacing around operators
        if '=' in line and not line.strip().startswith('#'):
            # Fix spacing around = operator
            line = re.sub(r'(\w)\s*=\s*(\w)', r'\1 = \2', line)
        
        formatted_lines.append(line)
        i += 1
    
    # Ensure proper blank lines
    final_lines = []
    prev_was_blank = False
    
    for i, line in enumerate(formatted_lines):
        is_blank = not line.strip()
        
        # Add double blank line before class/function definitions at module level
        if (line.startswith('class ') or line.startswith('def ') or 
            line.startswith('@app.')) and i > 0:
            if not prev_was_blank:
                final_lines.append('')
                final_lines.append('')
        
        # Don't add excessive blank lines
        if is_blank and prev_was_blank:
            continue
            
        final_lines.append(line)
        prev_was_blank = is_blank
    
    # Remove trailing blank lines and ensure single newline at end
    while final_lines and not final_lines[-1].strip():
        final_lines.pop()
    final_lines.append('')
    
    return '\n'.join(final_lines)

def format_file(file_path):
    """Format a single Python file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    formatted_content = apply_black_formatting(content)
    
    with open(file_path, 'w') as f:
        f.write(formatted_content)
    
    print(f"Formatted: {file_path}")

def main():
    """Format all Python files."""
    src_dir = Path("doorbell-addon/src")
    
    for py_file in src_dir.glob("*.py"):
        format_file(py_file)

if __name__ == "__main__":
    main()
