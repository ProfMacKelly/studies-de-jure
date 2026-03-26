import re
import os

# --- CONFIGURATION ---
INPUT_DIR = "input"
OUTPUT_DIR = "output"


def convert_all_caps_to_title(text):
    """
    Convert words in ALL CAPS to Title Case.
    Matches only 2+ letter uppercase words.
    """
    return re.sub(r'\b[A-Z]{2,}\b', lambda m: m.group(0).title(), text)


def transform_gitbook_markdown_links(text):
    """
    Transforms Markdown files that use [1](url) style footnotes
    into GitBook-compatible annotations.
    """

    # ------------------------------------------------------------
    # 1. HEADER CHAMELEON (same behavior as original script)
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # 2. INLINE FOOTNOTE CONVERSION
    #    [1](https://url) → GitBook annotation
    # ------------------------------------------------------------
    inline_pattern = r'\[(\d+)\]\([^)]+\)'

    inline_replacement = (
        r'[<sup>\1</sup>](#user-content-fn-\1)[^\1]'
    )

    body = re.sub(inline_pattern, inline_replacement, body)

    # ------------------------------------------------------------
    # 3. FOOTER: Markdown link references → GitBook footnotes
    #    [1]: https://example.com
    # ------------------------------------------------------------
    if footer.strip():
        footer_pattern = r'^\s*\[(\d+)\]:\s*(.+)$'

        footer = re.sub(
            footer_pattern,
            r'[^\1]: \2',
            footer,
            flags=re.MULTILINE
        )

        result = f"{body.strip()}\n\n{header}\n{footer.strip()}"
    else:
        result = body.strip()

    # ------------------------------------------------------------
    # 4. ALL CAPS → TITLE CASE (unchanged)
    # ------------------------------------------------------------
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

        with open(os.path.join(INPUT_DIR, filename), "r", encoding="utf-8") as f:
            content = f.read()

        processed = transform_gitbook_markdown_links(content)

        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write(processed)

    print(f"\nSuccess! {len(files)} files converted.")


if __name__ == "__main__":
    run_batch()