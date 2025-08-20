#!/usr/bin/env python3
"""Format Python code according to Black standards."""

import os
import re
from pathlib import Path

def format_python_file(file_path):
    """Format a Python file according to Black standards."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Apply basic Black formatting rules
    lines = content.split('\n')
    formatted_lines = []
    
    for i, line in enumerate(lines):
        # Remove trailing whitespace
        line = line.rstrip()
        
        # Fix import formatting
        if line.strip().startswith('from') and '(' in line and ')' not in line:
            # Multi-line import - ensure proper formatting
            if i + 1 < len(lines) and not lines[i + 1].strip().endswith(','):
                # Add trailing comma to last import
                j = i + 1
                while j < len(lines) and not lines[j].strip().endswith(')'):
                    if lines[j].strip() and not lines[j].strip().endswith(','):
                        lines[j] = lines[j].rstrip() + ','
                    j += 1
        
        # Fix function/class definitions
        if line.strip().endswith(':') and not line.endswith(':'):
            line = line.rstrip() + ':'
        
        # Ensure double blank lines before class/function definitions at module level
        if (line.startswith('class ') or line.startswith('def ')) and i > 0:
            if formatted_lines and formatted_lines[-1].strip():
                formatted_lines.append('')
                formatted_lines.append('')
        
        formatted_lines.append(line)
    
    # Remove excessive blank lines at end
    while formatted_lines and not formatted_lines[-1].strip():
        formatted_lines.pop()
    
    # Ensure file ends with single newline
    formatted_lines.append('')
    
    formatted_content = '\n'.join(formatted_lines)
    
    with open(file_path, 'w') as f:
        f.write(formatted_content)
    
    print(f"Formatted: {file_path}")

def main():
    """Format all Python files in the src directory."""
    src_dir = Path("doorbell-addon/src")
    
    if not src_dir.exists():
        print(f"Directory {src_dir} not found")
        return
    
    python_files = list(src_dir.glob("*.py"))
    
    for file_path in python_files:
        format_python_file(file_path)
    
    print(f"Formatted {len(python_files)} Python files")

if __name__ == "__main__":
    main()
