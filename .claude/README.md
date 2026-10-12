# Claude Code Utilities

Reusable slash commands and helper scripts for Claude Code. These cover session management (identifying and tracking sessions via a CSV registry), Jupyter notebook interaction (reading cells and finding inline instructions), conversation transcript search (regex search across JSONL session history with filtering and context), and git workflow helpers (conventional commit message generation).

## Setup

Some files contain placeholders that must be replaced with your own values before use. Find them with:

```bash
grep -rn '__USERNAME__\|__PROJECT__' .claude/
```

- `__USERNAME__` — your OS username (as it appears in your home directory path)
- `__PROJECT__` — a project-specific name used for temp/snapshot directories