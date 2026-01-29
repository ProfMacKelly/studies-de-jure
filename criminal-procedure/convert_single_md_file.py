
import re

# === USER CONFIGURATION ===
# Set the path to the Markdown file to convert
# Example: r"C:\User\mm\OneDrive\Documents\GitHub\Criminal-Procedure\autotesting\cases\example.md"
FILE_PATH = r"YOUR\FILE\PATH\HERE"

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
            while i < len(lines) and lines[i].startswith('>'):
                content_line = lines[i][1:].lstrip()
                output.append(f"    {content_line}")
                i += 1
        else:
            output.append(line)
            i += 1
    return '\n'.join(output)

def convert_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = convert_callouts(content)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Converted: {file_path}")

if __name__ == "__main__":
    if FILE_PATH == "YOUR\\FILE\\PATH\\HERE":
        print("❌ Please update FILE_PATH with your actual path.")
    else:
        convert_file(FILE_PATH)
