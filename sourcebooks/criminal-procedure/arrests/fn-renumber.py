import re
import sys
from pathlib import Path


# Matches inline GitBook-style annotation markers like:
# [<sup>5</sup>](#user-content-fn-5)[^5]
INLINE_FOOTNOTE_RE = re.compile(
    r'\[<sup>(\d+)</sup>\]\(#user-content-fn-(\d+)\)\[\^(\d+)\]'
)

# Matches footnote definition lines like:
# [^5]: Footnote text
DEFINITION_RE = re.compile(
    r'(?m)^\[\^(\d+)\]:(.*(?:\n(?!\[\^\d+\]:).*)*)'
)


def renumber_gitbook_footnotes(text: str):
    """
    Renumber GitBook-style inline annotation markers and matching footnote
    definition labels so numbering becomes sequential in the order the inline
    markers appear in the body text.

    Returns:
        new_text (str): transformed markdown
        mapping (dict[int, int]): old_number -> new_number
    """

    # Step 1: collect inline footnotes in body order
    matches = list(INLINE_FOOTNOTE_RE.finditer(text))
    if not matches:
        raise ValueError(
            "No inline GitBook-style footnote markers were found in the file."
        )

    old_numbers_in_order = []
    seen = set()

    for m in matches:
        n1, n2, n3 = m.groups()

        # Sanity check: the three numbers inside each marker should match
        if not (n1 == n2 == n3):
            raise ValueError(
                f"Mismatched inline marker found: {m.group(0)}\n"
                f"The three numbers inside the marker do not match."
            )

        old_num = int(n1)
        if old_num not in seen:
            seen.add(old_num)
            old_numbers_in_order.append(old_num)

    # Step 2: build old -> new mapping
    mapping = {old: new for new, old in enumerate(old_numbers_in_order, start=1)}

    # Step 3: replace inline markers
    def replace_inline(match: re.Match) -> str:
        old_num = int(match.group(1))
        new_num = mapping[old_num]
        return f'[<sup>{new_num}</sup>](#user-content-fn-{new_num})[^{new_num}]'

    new_text = INLINE_FOOTNOTE_RE.sub(replace_inline, text)

    # Step 4: replace footnote definition labels
    # Only labels are renumbered; footnote text itself is preserved.
    def replace_definition(match: re.Match) -> str:
        old_num = int(match.group(1))
        body = match.group(2)

        if old_num in mapping:
            new_num = mapping[old_num]
            return f'[^{new_num}]:{body}'
        else:
            # If a footnote definition exists at bottom but no surviving inline
            # reference points to it, remove it.
            return ''

    new_text = DEFINITION_RE.sub(replace_definition, new_text)

    # Step 5: clean up any large blank gaps left by removed unused definitions
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)

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
        output_path = input_path.with_name(input_path.stem + "_renumbered" + input_path.suffix)

    text = input_path.read_text(encoding="utf-8")

    try:
        new_text, mapping = renumber_gitbook_footnotes(text)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    output_path.write_text(new_text, encoding="utf-8")

    print(f"Done.")
    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print("\nRenumbering map:")
    for old_num, new_num in mapping.items():
        print(f"  {old_num} -> {new_num}")


if __name__ == "__main__":
    main()