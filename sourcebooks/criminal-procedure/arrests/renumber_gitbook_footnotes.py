import re
import sys
from pathlib import Path

# Matches inline GitBook-style markers like:
# [<sup>17</sup>](#user-content-fn-17)[^17]
INLINE_FOOTNOTE_RE = re.compile(
    r'\[<sup>(\d+)</sup>\]\(#user-content-fn-(\d+)\)\[\^(\d+)\]'
)

# Matches footnote definition lines like:
# [^17]: Footnote text
# including continuation lines until the next footnote definition
DEFINITION_RE = re.compile(
    r'(?ms)^\[\^(\d+)\]:(.*?)(?=^\[\^\d+\]:|\Z)'
)


def renumber_gitbook_footnotes(text: str):
    """
    Renumber GitBook-style inline footnote markers and matching footnote
    definition labels so numbering is sequential in the order the inline
    markers appear in the document.

    Returns:
        new_text (str)
        mapping (dict[int, int]) old_number -> new_number
    """

    # Find all inline markers in body order
    matches = list(INLINE_FOOTNOTE_RE.finditer(text))
    if not matches:
        raise ValueError(
            "No GitBook-style inline footnote markers were found."
        )

    old_numbers_in_order = []
    seen = set()

    for m in matches:
        sup_num, anchor_num, ref_num = m.groups()

        # Make sure all three numbers in one marker match
        if not (sup_num == anchor_num == ref_num):
            raise ValueError(
                f"Malformed marker with mismatched numbers:\n{m.group(0)}"
            )

        old_num = int(sup_num)
        if old_num not in seen:
            seen.add(old_num)
            old_numbers_in_order.append(old_num)

    # Build mapping based on surviving body order
    mapping = {
        old_num: new_num
        for new_num, old_num in enumerate(old_numbers_in_order, start=1)
    }

    # Replace every inline marker fully
    def replace_inline(match: re.Match) -> str:
        old_num = int(match.group(1))
        new_num = mapping[old_num]
        return f'[<sup>{new_num}</sup>](#user-content-fn-{new_num})[^{new_num}]'

    new_text = INLINE_FOOTNOTE_RE.sub(replace_inline, text)

    # Replace footnote definition labels at bottom
    def replace_definition(match: re.Match) -> str:
        old_num = int(match.group(1))
        body = match.group(2)

        # Keep only definitions that still have a surviving inline reference
        if old_num in mapping:
            new_num = mapping[old_num]
            return f'[^{new_num}]:{body}'
        return ''

    new_text = DEFINITION_RE.sub(replace_definition, new_text)

    # Clean up excessive blank lines that may result from removed definitions
    new_text = re.sub(r'\n{3,}', '\n\n', new_text).rstrip() + '\n'

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