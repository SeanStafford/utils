#!/usr/bin/env python3
"""Read specific cells from a Jupyter notebook by 1-indexed cell number.

Usage:
    python read_notebook_cells.py <notebook_path> <cell_spec> [snapshot_dir]

Cell spec examples:
    5           Single cell
    5,8,12      Multiple cells
    5-10        Range (inclusive)
    5-10,15,20  Mixed

If snapshot_dir is provided, saves each cell's source to a file in that directory
for later reference (e.g., to detect if a cell changed between read and edit).
If none provided, defaults to saving in /tmp/
"""

import json
import os
import re
import sys
from datetime import datetime

DEFAULT_SNAPSHOT_BASE = "/tmp/"
SNAPSHOT_SUBDIR = "notebook_snapshots"


def parse_cell_spec(spec):
    """Parse cell spec like '5', '5,8,12', '5-10', '5-10,15' into sorted list of 1-indexed numbers."""
    numbers = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            numbers.update(range(int(start), int(end) + 1))
        else:
            numbers.add(int(part))
    return sorted(numbers)


def make_filepath_safe(spec):
    """Convert a cell spec like '5-10,15' into a filesystem-safe string."""
    return re.sub(r"[^\w\-]", "_", spec)


def main():
    if len(sys.argv) < 3:
        print("Usage: read_notebook_cells.py <notebook_path> <cell_spec> [snapshot_base_dir]", file=sys.stderr)
        print("  e.g.: read_notebook_cells.py nb.ipynb 5-10 /tmp/__PROJECT__/", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    cell_spec = sys.argv[2]
    snapshot_base = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SNAPSHOT_BASE

    with open(path) as f:
        nb = json.load(f)

    # Snapshot dir: <base>/notebook_snapshots/<notebook_name>/
    nb_name = os.path.splitext(os.path.basename(path))[0]
    snap_path = os.path.join(snapshot_base, SNAPSHOT_SUBDIR, nb_name)
    os.makedirs(snap_path, exist_ok=True)

    total = len(nb["cells"])
    requested = parse_cell_spec(cell_spec)

    # Build output lines for both display and snapshot
    output_lines = []
    for cell_num in requested:
        if cell_num < 1 or cell_num > total:
            line = f"Cell {cell_num}: OUT OF RANGE (notebook has {total} cells)\n"
            output_lines.append(line)
            print(line)
            continue

        cell = nb["cells"][cell_num - 1]
        cell_id = cell.get("id", "no-id")
        cell_type = cell.get("cell_type", "unknown")
        source = "".join(cell["source"])

        header = f"{'=' * 70}\nCell {cell_num} (id: {cell_id}, type: {cell_type})\n{'=' * 70}"
        output_lines.append(header)
        output_lines.append(source)
        output_lines.append("")

        print(header)
        print(source)
        print()

    # Save all cells to one snapshot file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_spec = make_filepath_safe(cell_spec)
    snap_file = os.path.join(snap_path, f"cells_{safe_spec}_{timestamp}.txt")
    with open(snap_file, "w") as sf:
        sf.write("\n".join(output_lines))

    print(f"Snapshot saved to: {snap_file}")


if __name__ == "__main__":
    main()
