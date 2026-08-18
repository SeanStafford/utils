---
description: Read specific cells from a Jupyter notebook by 1-indexed cell number
allowed-tools: Bash(python ~/.claude/scripts/read_notebook_cells.py:*)
---

Read specific cells from a Jupyter notebook by 1-indexed cell number.

**Arguments:** `$ARGUMENTS`

**Instructions:**
1. Parse `$ARGUMENTS` for a notebook path and cell spec:
   - If both are provided (e.g., `notebooks/foo.ipynb 5-10`), use them directly
   - If only a cell spec is provided (e.g., `5-10`), use the most recently relevant notebook from context
   - If only a path is provided, list all cells as a summary
2. Run `python ~/.claude/scripts/read_notebook_cells.py <notebook_path> <cell_spec> /tmp/__PROJECT__/`
   - Cell specs: `5` (single), `5,8,12` (multiple), `5-10` (range), `5-10,15` (mixed)
   - Snapshots are saved to `/tmp/__PROJECT__/notebook_snapshots/<notebook_name>/`
3. Display the output to the user