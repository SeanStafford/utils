#!/usr/bin/env python3
"""Find cells in a Jupyter notebook containing '# Claude:' instructions.

Usage:
    python find_notebook_instructions.py <notebook_path>

Prints each matching cell's index (1-indexed), cell ID, and full source.
"""

import json
import re
import sys

DEFAULT_SIGNAL_PATTERN = re.compile(r"#\s*Claude:", re.IGNORECASE)


def main():
    if len(sys.argv) == 3:
        signal_pattern = re.compile(sys.argv[2], re.IGNORECASE)
    elif len(sys.argv) == 2:
        signal_pattern = DEFAULT_SIGNAL_PATTERN
    else:
        print("Usage: find_notebook_instructions.py <notebook_path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        nb = json.load(f)

    cell_matches = []
    line_matches = []

    for i, cell in enumerate(nb["cells"], start=1):
        source = "".join(cell["source"])
        if signal_pattern.search(source):
            cell_id = cell.get("id", "no-id")
            cell_type = cell.get("cell_type", "unknown")
            cell_matches.append((i, cell_id, cell_type, source))

            for j, line in enumerate(cell["source"]):
                if signal_pattern.search(line):
                    line_matches.append((i, cell_id, j, line.strip()))

    if not cell_matches:
        print("No cells found with signal pattern.")
        return

    if len(line_matches) != len(cell_matches):
        print(
            f"\nFound {len(line_matches)} instructions across {len(cell_matches)} cell(s):\n"
        )
    else:
        print(f"\nFound {len(cell_matches)} cell(s) with instructions:\n")

    # Summary
    for i, (cell_num, _, _, text) in enumerate(line_matches, start=1):
        cell_prefix_text = f" (Cell {cell_num})" if len(cell_matches) > 1 else ""
        prefix_text = f"  Instruction #{i:<2d}{cell_prefix_text}"
        instruction = re.split(signal_pattern, text, 1)[-1].strip()
        print(f"{prefix_text}: {instruction}")

    # Full contents
    for cell_num, cell_id, cell_type, source in cell_matches:
        print(f"\n{'=' * 70}")
        print(f"Cell {cell_num} (id: {cell_id}, type: {cell_type})")
        print(f"{'=' * 70}")
        print(source)
    print()


if __name__ == "__main__":
    main()
