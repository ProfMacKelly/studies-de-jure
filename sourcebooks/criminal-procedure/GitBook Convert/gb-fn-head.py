import re
import os

# --- CONFIGURATION ---
INPUT_DIR = "input"
OUTPUT_DIR = "output"

def convert_all_caps_to_title(text):
    """
    Convert words in ALL CAPS to Title Case.
    Matches only 2+ letter uppercase words, so single letters like 'A' or 'I'
    are left alone.
    """
    return re.sub(r'\b[A-Z]{2,}\b', lambda m: m.group(0).title(), text)

def transform_gitbook_textbook(text):
    # 1. THE HEADER CHAMELEON (Flexible Header Split)
    # Splits at any # heading level (H1-H6) for References or Footnotes.
    header_pattern = r'(?im)^(#+\s+(?:References|Footnotes).*)$'
    parts = re.split(header_pattern, text, maxsplit=1)
    
    if len(parts) < 3:
        body = text
        header = "## References"  # Default
        footer = ""
    else:
        body = parts[0]
        header = parts[1]
        footer = parts[2]

    # 2. THE "SPACE-EATER" & "URL-PURGE"
    # Logic Breakdown:
    # [ \t]* -> Swallow horizontal spaces before the bracket.
    # \[(\d+)\] -> Capture the number [1].
    # (?:\s*\((?:\\.|[^()])*\))? -> OPTIONALLY find and swallow (...) after the [1].
    # Handles escaped parens like \(Alvarez\).
    body_pattern = r'[ \t]*\[(\d+)\](?:\s*\((?:\\.|[^()])*\))?'
    
    # Replacement: Only the captured number (\1) is used; the space and URL are discarded.
    body_replacement = r'<sup>[\1](#user-content-fn-\1)[^\1]</sup>'
    body = re.sub(body_pattern, body_replacement, body)

    # 3. FOOTER STANDARDIZATION
    if footer.strip():
        # Standardize '1. ', '[1]: ', or '1) ' at the start of a line to '[^1]: '
        footer_label_pattern = r'^\s*(?:\[\^?)?(\d+)(?:\][:.]|[.):])\s+'
        footer = re.sub(footer_label_pattern, r'[^\1]: ', footer, flags=re.MULTILINE)
        
        result = f"{body.strip()}\n\n{header}\n{footer.strip()}"
    else:
        result = body.strip()

    # 4. CONVERT ALL-CAPS WORDS TO TITLE CASE
    result = convert_all_caps_to_title(result)

    return result

def run_batch():
    for folder in [INPUT_DIR, OUTPUT_DIR]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".md")]
    
    if not files:
        print(f"No .md files found in '{INPUT_DIR}'.")
        return

    for filename in files:
        print(f"Processing: {filename}...")
        with open(os.path.join(INPUT_DIR, filename), 'r', encoding='utf-8') as f:
            content = f.read()

        processed_content = transform_gitbook_textbook(content)

        with open(os.path.join(OUTPUT_DIR, filename), 'w', encoding='utf-8') as f:
            f.write(processed_content)
    
    print(f"\nSuccess! {len(files)} files converted.")

if __name__ == "__main__":
    run_batch()