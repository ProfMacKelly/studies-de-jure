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


def convert_headings_to_title_case(text):
    """
    Convert Markdown headings (# through ######) to Title Case,
    preserving the leading # symbols.
    Example:
        ## ARRESTS -> ## Arrests
        ### probable cause -> ### Probable Cause
    """
    def replace_heading(match):
        hashes = match.group(1)
        heading_text = match.group(2).strip()
        return f"{hashes} {heading_text.title()}"

    return re.sub(r'^(#{1,6})\s+(.*)$', replace_heading, text, flags=re.MULTILINE)


def transform_gitbook_textbook(text):
    # 1. Split at References / Footnotes heading (H1-H6)
    header_pattern = r'(?im)^(#+\s+(?:References|Footnotes).*)$'
    parts = re.split(header_pattern, text, maxsplit=1)

    if len(parts) < 3:
        body = text
        header = "## References"
        footer = ""
    else:
        body = parts[0]
        header = parts[1]
        footer = parts[2]

    # 2. Convert in-body markdown-linked footnote markers:
    #    [1](https://example.com/...)  ->  [<sup>1</sup>](#user-content-fn-1)[^1]
    #
    #    This pattern tolerates escaped parentheses inside the URL, such as \(Alvarez\)
    body_link_pattern = r'\[(\d+)\]\((?:\\.|[^()])*\)'

    def replace_body_link(match):
        n = match.group(1)
        return f'[<sup>{n}</sup>](#user-content-fn-{n})[^{n}]'

    body = re.sub(body_link_pattern, replace_body_link, body)

    # Optional fallback:
    # If any plain [1] style markers remain in the body, convert them too,
    # but avoid touching already-normalized [^1] footnotes.
    body_plain_pattern = r'(?<!\^)\[(\d+)\](?!\()'

    def replace_body_plain(match):
        n = match.group(1)
        return f'[<sup>{n}</sup>](#user-content-fn-{n})[^{n}]'

    body = re.sub(body_plain_pattern, replace_body_plain, body)

    # 3. Standardize footer/reference labels:
    #    1. text
    #    1) text
    #    [1]: text
    #    -> [^1]: text
    if footer.strip():
        footer_label_pattern = r'^\s*(?:\[\^?)?(\d+)(?:\][:.]|[.):])\s+'
        footer = re.sub(footer_label_pattern, r'[^\1]: ', footer, flags=re.MULTILINE)
        result = f"{body.strip()}\n\n{header}\n{footer.strip()}"
    else:
        result = body.strip()

    # 4. Convert all Markdown headings to Title Case
    result = convert_headings_to_title_case(result)

    # 5. Convert ALL-CAPS words to Title Case
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
        input_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        processed_content = transform_gitbook_textbook(content)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(processed_content)

    print(f"\nSuccess! {len(files)} files converted.")


if __name__ == "__main__":
    run_batch()