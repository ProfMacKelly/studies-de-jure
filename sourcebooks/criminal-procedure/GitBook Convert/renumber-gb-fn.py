import re
import sys
from pathlib import Path

# Matches inline GitBook-style markers like:
# [<sup>17</sup>](#user-content-fn-17)[^17]
INLINE_FOOTNOTE_RE = re.compile(
    r'\[<sup>(\d+)</sup>\]\(#user-content-fn-(\d+)\)\[\^(\d+)\]'
)

# Matches footnote definition blocks like:
# [^17]: Footnote text
#     continuation line
# More continuation text
#
# stopping before the next footnote definition or end of file
DEFINITION_BLOCK_RE = re.compile(
    r'(?ms)^\[\^(\d+)\]:(.*?)(?=^\[\^\d+\]:|\Z)'
)

# Matches a trailing Markdown heading that should be treated as the
# footnote/reference heading if it sits immediately before the definitions.
FOOTNOTE_HEADING_RE = re.compile(
    r'(?im)^(#{1,6}\s+(?:References|Footnotes))\s*$'
)


def split_body_and_existing_heading(text: str, first_definition_start: int):
    """
    Split the document into:
      - body before the footnote section
      - an optional existing References/Footnotes heading immediately
        preceding the definitions

    Assumes footnote definitions are at the bottom of the file.
    """
    pre_defs = text[:first_definition_start].rstrip()

    lines = pre_defs.splitlines()
    i = len(lines) - 1

    # Skip trailing blank lines
    while i >= 0 and not lines[i].strip():
        i -= 1

    if i >= 0 and FOOTNOTE_HEADING_RE.match(lines[i].strip()):
        heading = lines[i].strip()
        body = "\n".join(lines[:i]).rstrip()
        return body, heading

    return pre_defs.rstrip(), None


def extract_definition_map(text: str):
    """
    Extract all footnote definitions into a dictionary:
        old_number -> definition body

    Raises an error if duplicate definition numbers are found.
    """
    definitions = {}
    matches = list(DEFINITION_BLOCK_RE.finditer(text))

    for match in matches:
        old_num = int(match.group(1))
        body = match.group(2).rstrip()

        if old_num in definitions:
            raise ValueError(
                f"Duplicate footnote definition found for [^{old_num}]."
            )

        definitions[old_num] = body

    return definitions, matches


def renumber_gitbook_footnotes(text: str):
    """
    Renumber GitBook-style inline footnote markers and rebuild the footnote
    definition list at the bottom in the new order of appearance.

    This solves both:
      1. numbering gaps
      2. markers becoming out of order after text is moved around

    Returns:
        new_text (str)
        mapping (dict[int, int]) old_number -> new_number
    """
    inline_matches = list(INLINE_FOOTNOTE_RE.finditer(text))
    if not inline_matches:
        raise ValueError(
            "No GitBook-style inline footnote markers were found."
        )

    # Read inline markers in current body order and validate each one.
    old_numbers_in_order = []
    seen = set()

    for match in inline_matches:
        sup_num, anchor_num, ref_num = match.groups()

        if not (sup_num == anchor_num == ref_num):
            raise ValueError(
                f"Malformed marker with mismatched numbers:\n{match.group(0)}"
            )

        old_num = int(sup_num)
        if old_num not in seen:
            seen.add(old_num)
            old_numbers_in_order.append(old_num)

    mapping = {
        old_num: new_num
        for new_num, old_num in enumerate(old_numbers_in_order, start=1)
    }

    # Extract definition blocks from the original document.
    definitions, def_matches = extract_definition_map(text)

    if not def_matches:
        raise ValueError(
            "No footnote definitions like [^1]: ... were found."
        )

    # Make sure every referenced inline note has a matching definition.
    missing = [old_num for old_num in old_numbers_in_order if old_num not in definitions]
    if missing:
        missing_str = ", ".join(f"[^{n}]" for n in missing)
        raise ValueError(
            f"Missing matching footnote definition(s) for: {missing_str}"
        )

    # Split body from existing footer area based on first definition.
    first_definition_start = def_matches[0].start()
    body, existing_heading = split_body_and_existing_heading(text, first_definition_start)

    # Rewrite inline markers everywhere in the body.
    def replace_inline(match: re.Match) -> str:
        old_num = int(match.group(1))
        new_num = mapping[old_num]
        return f'[<sup>{new_num}</sup>](#user-content-fn-{new_num})[^{new_num}]'

    new_body = INLINE_FOOTNOTE_RE.sub(replace_inline, body).rstrip()

    # Rebuild the footnote section from scratch, in the new body order.
    heading = existing_heading or "## References"

    rebuilt_definitions = []
    for old_num in old_numbers_in_order:
        new_num = mapping[old_num]
        def_body = definitions[old_num]
        rebuilt_definitions.append(f'[^{new_num}]:{def_body}')

    footer = "\n\n".join(rebuilt_definitions).rstrip()

    if footer:
        new_text = f"{new_body}\n\n{heading}\n\n{footer}\n"
    else:
        new_text = new_body.rstrip() + "\n"

    # Normalize excessive blank lines, but preserve standard paragraph spacing.
    new_text = re.sub(r'\n{4,}', '\n\n\n', new_text)

    return new_text, mapping


def main():
    if len(sys.argv) < 2:
        print("Usage: python renumber_gitbook_footnotes.py input.md [output.md]")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name(
            f"{input_path.stem}_renumbered{input_path.suffix}"
        )

    text = input_path.read_text(encoding="utf-8")

    try:
        new_text, mapping = renumber_gitbook_footnotes(text)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    output_path.write_text(new_text, encoding="utf-8")

    print("Done.")
    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print("\nRenumbering map:")
    for old_num, new_num in mapping.items():
        print(f"  {old_num} -> {new_num}")


if __name__ == "__main__":
    main()