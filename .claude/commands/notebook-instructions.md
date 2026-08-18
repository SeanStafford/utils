---
description: Find and execute '# Claude:' instructions left in a Jupyter notebook
allowed-tools: Bash(python ~/.claude/scripts/find_notebook_instructions.py:*), Bash(python ~/.claude/scripts/read_notebook_cells.py:*), Read, NotebookEdit
---

Find and execute instructions the user has left in a Jupyter notebook as `# Claude:` comments.

**Arguments:** `$ARGUMENTS`

**Instructions:**
1. Determine the notebook path:
   - If `$ARGUMENTS` contains a path, use it
   - If `$ARGUMENTS` is empty, look for the most recently modified `.ipynb` file in the `notebooks/` directory or use common sense based on context
2. Run `python ~/.claude/scripts/find_notebook_instructions.py <notebook_path>` to find all cells with `# Claude:` instructions
3. Use `python ~/.claude/scripts/read_notebook_cells.py <notebook_path> <cell_spec> /tmp/__PROJECT__/` to read the flagged cells and their neighbors for context. This saves snapshots to `/tmp/__PROJECT__/notebook_snapshots/`. Cell specs support ranges (e.g., `18-25`) and comma-separated lists (e.g., `5,10,15`). Do NOT use `python -c` or other Bash commands to read notebook contents.
4. For each flagged cell, follow the instruction in the `# Claude:` comment:
   - Edit the cell as requested using NotebookEdit
   - Remove the `# Claude:` comment line after completing the instruction
5. Summarize what was changed