import re
import os
import argparse
from collections import OrderedDict

# --- CONFIGURATION ---
INPUT_DIR = "input"
OUTPUT_DIR = "output"


def warn(msg):
    print(f"[WARN] {msg}")


def info(msg):
    print(f"[INFO] {msg}")


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
    """
    def replace_heading(match):
        hashes = match.group(1)
        heading_text = match.group(2).strip()
        return f"{hashes} {heading_text.title()}"

    return re.sub(r'^(#{1,6})\s+(.*)$', replace_heading, text, flags=re.MULTILINE)


def split_body_and_footer(text):
    """
    Split the document at the first heading named References or Footnotes.
    Returns:
        body, header, footer

    If no such heading exists, the whole document is treated as body and a
    default '## References' heading is supplied for later use if needed.
    """
    header_pattern = r'(?im)^(#{1,6}\s+(?:References|Footnotes).*)$'
    parts = re.split(header_pattern, text, maxsplit=1)

    if len(parts) < 3:
        warn("No References/Footnotes heading found; treating entire file as body.")
        return text, "## References", ""

    return parts[0], parts[1].strip(), parts[2]


def protect_or_remove_google_scholar_page_markers(text, page_mode="preserve"):
    """
    Detect Google Scholar print-page markers of the form:

        [70](url)[\\*70](url)

    where both numbers must match.

    Behavior:
      - preserve: replace with temporary tokens so footnote processing ignores them,
                  then restore them later
      - delete: remove them entirely before footnote processing

    Returns:
        new_text, page_marker_map, count
    """
    pattern = re.compile(
        r'\[(\d+)\]\((?:\\.|[^()])*\)\[\\\*(\d+)\]\((?:\\.|[^()])*\)'
    )

    page_marker_map = OrderedDict()
    count = 0

    def replace(match):
        nonlocal count
        first_num, second_num = match.group(1), match.group(2)

        # Only treat it as a page-marker pair if both numbers match exactly.
        if first_num != second_num:
            return match.group(0)

        count += 1

        if page_mode == "delete":
            return ""

        token = f"<<GS_PAGE_{count}>>"
        page_marker_map[token] = match.group(0)
        return token

    new_text = pattern.sub(replace, text)

    if count:
        action = "Preserved" if page_mode == "preserve" else "Deleted"
        info(f"{action} {count} Google Scholar page-marker pair(s).")
    else:
        info("Detected 0 Google Scholar page-marker pairs.")

    return new_text, page_marker_map, count


def restore_google_scholar_page_markers(text, page_marker_map):
    """
    Restore previously protected Google Scholar page-marker tokens.
    """
    for token, original in page_marker_map.items():
        text = text.replace(token, original)
    return text


def normalize_body_markers_to_tokens(body):
    """
    Replace all supported inline footnote markers in the body with canonical
    temporary tokens of the form <<FN:n>>.

    Supported input forms:
      - [1](url)
      - [\\[1\\]](url)
      - [1]
      - [<sup>1</sup>](#user-content-fn-1)[^1]

    The GitBook-style form is validated to make sure all three numbers match.
    """
    gitbook_pattern = re.compile(
        r'\[<sup>(\d+)</sup>\]\(#user-content-fn-(\d+)\)\[\^(\d+)\]'
    )
    body_link_pattern = re.compile(
        r'\[(\d+)\]\((?:\\.|[^()])*\)'
    )
    body_escaped_link_pattern = re.compile(
        r'\[\\\[(\d+)\\\]\]\((?:\\.|[^()])*\)'
    )
    body_plain_pattern = re.compile(
        r'(?<!\^)\[(\d+)\](?!\()'
    )

    marker_count = 0

    def replace_gitbook(match):
        nonlocal marker_count
        sup_num, anchor_num, ref_num = match.groups()
        if not (sup_num == anchor_num == ref_num):
            raise ValueError(
                f"Malformed GitBook inline marker with mismatched numbers:\n{match.group(0)}"
            )
        marker_count += 1
        return f"<<FN:{sup_num}>>"

    def replace_simple(match):
        nonlocal marker_count
        n = match.group(1)
        marker_count += 1
        return f"<<FN:{n}>>"

    # Order matters
    body = gitbook_pattern.sub(replace_gitbook, body)
    body = body_link_pattern.sub(replace_simple, body)
    body = body_escaped_link_pattern.sub(replace_simple, body)
    body = body_plain_pattern.sub(replace_simple, body)

    if marker_count == 0:
        warn("No inline footnote markers detected in body.")
    else:
        info(f"Detected {marker_count} inline footnote marker(s).")

    return body, marker_count


def match_definition_start(line):
    """
    Return a regex match if the line starts a supported footnote definition.

    Supported starts:
      - [^1]&#58; text
      - [1]&#58; text
      - [1]. text
      - 1. text
      - 1) text
      - 1: text
      - [\\[1\\]](url) text

    Returns None if no supported definition start is found.
    """
    patterns = [
        # [\[1\]](url) text
        re.compile(r'^\s*\[\\\[(\d+)\\\]\]\((?:\\.|[^()])*\)\s+(.*)$'),

        # [^1]: text  or  [1]: text  or  [1]. text
        re.compile(r'^\s*\[\^?(\d+)\](?:[:.])\s+(.*)$'),

        # 1. text  or  1) text  or  1: text
        re.compile(r'^\s*(\d+)[\.\):]\s+(.*)$'),
    ]

    for pattern in patterns:
        match = pattern.match(line)
        if match:
            return match

    return None


def parse_footer_definitions(footer):
    """
    Parse footer definitions into an OrderedDict:
        original_number (str) -> definition_text (str)

    Supports multiline definitions by attaching all non-definition-start lines
    after a definition to that definition until the next definition start.

    Always fatal on duplicate numbers.
    """
    definitions = OrderedDict()

    if not footer.strip():
        warn("No footer definitions detected.")
        return definitions

    lines = footer.splitlines()
    current_number = None
    current_lines = []

    def flush_current():
        nonlocal current_number, current_lines
        if current_number is not None:
            if current_number in definitions:
                raise ValueError(
                    f"Duplicate footnote definition found for [^{current_number}]."
                )
            definitions[current_number] = "\n".join(current_lines).rstrip()
        current_number = None
        current_lines = []

    for line in lines:
        start_match = match_definition_start(line)

        if start_match:
            flush_current()
            current_number = start_match.group(1)
            current_lines = [start_match.group(2)]
        else:
            if current_number is not None:
                current_lines.append(line)
            else:
                # Ignore stray text before the first recognized definition.
                continue

    flush_current()

    info(f"Parsed {len(definitions)} footnote definition(s).")
    return definitions


def renumber_body_and_rebuild_footer(body_with_tokens, footer_definitions, mode="strict"):
    """
    Renumber footnotes by first appearance order in the body.

    Returns:
        new_body, new_footer, mapping

    mode:
      - strict: missing definitions are fatal
      - lenient: missing definitions are warned about and emitted as blanks
    """
    token_pattern = re.compile(r'<<FN:(\d+)>>')

    old_numbers_in_order = []
    seen = set()

    for match in token_pattern.finditer(body_with_tokens):
        old_n = match.group(1)
        if old_n not in seen:
            seen.add(old_n)
            old_numbers_in_order.append(old_n)

    if not old_numbers_in_order:
        warn("No footnotes to renumber.")
        return body_with_tokens, "", {}

    missing = [old_n for old_n in old_numbers_in_order if old_n not in footer_definitions]
    if missing:
        missing_str = ", ".join(f"[^{n}]" for n in missing)
        if mode == "strict":
            raise ValueError(
                f"Missing matching footnote definition(s) for: {missing_str}"
            )
        warn(
            f"Missing matching footnote definition(s) for: {missing_str}. "
            f"Blank placeholder definition(s) will be emitted."
        )
        for old_n in missing:
            footer_definitions[old_n] = ""

    mapping = {
        old_n: str(i + 1)
        for i, old_n in enumerate(old_numbers_in_order)
    }

    def replace_token(match):
        old_n = match.group(1)
        new_n = mapping[old_n]
        return f'[<sup>{new_n}</sup>](#user-content-fn-{new_n})[^{new_n}]'

    new_body = token_pattern.sub(replace_token, body_with_tokens)

    rebuilt_definitions = []

    for old_n in old_numbers_in_order:
        new_n = mapping[old_n]
        def_text = footer_definitions[old_n]
        rebuilt_definitions.append(f'[^{new_n}]: {def_text}'.rstrip())

    unreferenced = [n for n in footer_definitions.keys() if n not in mapping]

    if unreferenced:
        warn(f"{len(unreferenced)} unreferenced footnote definition(s) preserved.")
        if rebuilt_definitions:
            rebuilt_definitions.append("")

        next_num = len(old_numbers_in_order) + 1
        for old_n in unreferenced:
            def_text = footer_definitions[old_n]
            rebuilt_definitions.append(f'[^{next_num}]: {def_text}'.rstrip())
            next_num += 1

    new_footer = "\n".join(rebuilt_definitions).rstrip()

    return new_body, new_footer, mapping


def cleanup_deleted_page_marker_whitespace(text):
    """
    Optional cleanup after deleting page markers.
    Keeps this conservative so it does not disturb normal paragraph structure.
    """
    # Collapse 3+ spaces into 1
    text = re.sub(r'[ \t]{3,}', ' ', text)

    # Remove spaces left before punctuation after deletion
    text = re.sub(r'[ \t]+([,.;:!?])', r'\1', text)

    return text


def transform_gitbook_textbook(text, mode="strict", page_mode="preserve"):
    """
    Full pipeline:
      1. split body/footer
      2. protect or delete Google Scholar page-marker pairs in body
      3. normalize supported inline footnote markers to tokens
      4. parse supported footer definition formats
      5. renumber in body order
      6. rebuild body in GitBook style
      7. rebuild footer in [^n]: form
      8. restore preserved page markers if needed
      9. apply heading/all-caps cleanup
    """
    body, header, footer = split_body_and_footer(text)

    body, page_marker_map, page_marker_count = protect_or_remove_google_scholar_page_markers(
        body,
        page_mode=page_mode
    )

    body_with_tokens, marker_count = normalize_body_markers_to_tokens(body)
    footer_definitions = parse_footer_definitions(footer)

    new_body, new_footer, mapping = renumber_body_and_rebuild_footer(
        body_with_tokens,
        footer_definitions,
        mode=mode
    )

    if page_mode == "preserve":
        new_body = restore_google_scholar_page_markers(new_body, page_marker_map)
    else:
        new_body = cleanup_deleted_page_marker_whitespace(new_body)

    if new_footer.strip():
        result = f"{new_body.strip()}\n\n{header}\n{new_footer.strip()}"
    else:
        result = new_body.strip()

    result = convert_headings_to_title_case(result)
    result = convert_all_caps_to_title(result)

    return result, mapping, marker_count, len(footer_definitions), page_marker_count


def parse_args():
    parser = argparse.ArgumentParser(
        description="Normalize and auto-renumber Markdown/GitBook-style footnotes."
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing referenced definitions as fatal errors (default behavior)."
    )
    mode_group.add_argument(
        "--lenient",
        action="store_true",
        help="Allow missing referenced definitions and emit blank placeholder footnotes."
    )

    parser.add_argument(
        "--page-markers",
        choices=["preserve", "delete"],
        default="preserve",
        help=(
            "How to handle Google Scholar print-page markers of the form "
            "[70](url)[\\*70](url): "
            "'preserve' keeps them in output but excludes them from footnote processing; "
            "'delete' removes them entirely."
        )
    )

    parser.add_argument(
        "--input-dir",
        default=INPUT_DIR,
        help=f"Directory containing input .md files (default: {INPUT_DIR})"
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help=f"Directory for output .md files (default: {OUTPUT_DIR})"
    )

    return parser.parse_args()


def run_batch(input_dir, output_dir, mode="strict", page_mode="preserve"):
    for folder in [input_dir, output_dir]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    files = [f for f in os.listdir(input_dir) if f.endswith(".md")]

    if not files:
        warn(f"No .md files found in '{input_dir}'.")
        return

    info(f"Running in {mode.upper()} mode.")
    info(f"Google Scholar page-marker handling: {page_mode.upper()}.")

    for filename in files:
        print(f"\n=== Processing: {filename} ===")
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            (
                processed_content,
                mapping,
                marker_count,
                def_count,
                page_marker_count,
            ) = transform_gitbook_textbook(
                content,
                mode=mode,
                page_mode=page_mode
            )
        except ValueError as e:
            print(f"[ERROR] {e}")
            continue

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(processed_content)

        info(f"Wrote output: {output_path}")
        info(f"Inline footnote marker count: {marker_count}")
        info(f"Footnote definition count: {def_count}")
        info(f"Google Scholar page-marker pair count: {page_marker_count}")

        if mapping:
            print("Renumbering map:")
            for old_num, new_num in mapping.items():
                print(f"  {old_num} -> {new_num}")

    print("\nDone.")


if __name__ == "__main__":
    args = parse_args()

    mode = "strict"
    if args.lenient:
        mode = "lenient"
    elif args.strict:
        mode = "strict"

    run_batch(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        mode=mode,
        page_mode=args.page_markers
    )