
import os
import re

# === USER CONFIGURATION ===
# Set the path to the root folder containing your .md files
# Example: r"C:\User\mm\OneDrive\Documents\GitHub\Criminal-Procedure\autotesting\cases"
ROOT_DIR = r"YOUR\PATH\HERE"

# List of supported callouts to convert
CALLOUT_TYPES = ['NOTE', 'TIP', 'WARNING', 'IMPORTANT', 'CAUTION']

# ===========================

def convert_callouts(content):
    lines = content.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r'^> \[!(\w+)\](.*)', line)
        if match and match.group(1).upper() in CALLOUT_TYPES:
            callout_type = match.group(1).lower()
            text = match.group(2).strip()
            output.append(f"!!! {callout_type}")
            output.append(f"    {text}")
            i += 1
            # Handle additional indented lines
            while i < len(lines) and lines[i].startswith('>'):
                content_line = lines[i][1:].lstrip()
                output.append(f"    {content_line}")
                i += 1
        else:
            output.append(line)
            i += 1
    return '\n'.join(output)

def process_md_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = convert_callouts(content)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Converted: {filepath}")

def convert_all_md_files(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.md'):
                full_path = os.path.join(dirpath, filename)
                process_md_file(full_path)

if __name__ == "__main__":
    if ROOT_DIR == "YOUR\\PATH\\HERE":
        print("❌ Please update ROOT_DIR with your actual path.")
    else:
        convert_all_md_files(ROOT_DIR)
