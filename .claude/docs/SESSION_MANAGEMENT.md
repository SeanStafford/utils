# Session Management

Lightweight tracking layer on top of Claude Code's native session persistence.

## Purpose

Claude Code persists sessions automatically, but finding the right session among many is difficult. This system adds:
- Human-readable session registry with descriptions
- Per-session summary files for context recovery
- Status tracking (active, completed, paused, abandoned)

## Directory Structure

```
.claude/
└── sessions/            # session tracking
    ├── registry.csv     # session metadata
    └── {name}.md       # per-session markdown files
```

## Registry Format

CSV file in the project root directory at `.claude/sessions/registry.csv`:

```csv
session_id,name,status,created,updated,description
682ea0e3-3e28-4e88-8475-77d0ae8c6d12,session-naming,completed,2026-01-01T11:00,2026-01-01T11:30,setting up session tracking infrastructure
abc123-4567-89de-f012-3456789abcde,my-feature,active,?,2026-01-01T16:30,implementing new feature with iterative refinement
,unnamed-dec30,paused,2025-12-30T16:00,2025-12-30T17:00,exploring embedding approaches
```

Fields:
- **session_id**: Claude Code's internal UUID (from .jsonl filename). Empty if internal ID not yet determined.
- **name**: User-assigned name from `/rename` command, or informal identifier
- **status**: `active` | `completed` | `paused` | `abandoned`
- **created**: ISO timestamp (date + hour:minute), or `?` if unknown
- **updated**: ISO timestamp of last activity
- **description**: One-line summary of session purpose

**Determining session_id**: Use `/get-session-id` to find the current session's internal UUID. This enables linking the registry to Claude Code's native session files.

## Summary Files

Markdown files in the project root directory at `.claude/sessions/{name}.md`:

```markdown
# Session: my-feature

**Status**: completed
**Created**: 2025-12-28T09:00
**Updated**: 2025-12-28T14:00

## Purpose
Implement job description parser for intake context.

## Key Decisions
- Used spaCy for NER extraction
- Structured output as NormalizedJob dataclass

## Files Modified
- src/parser.py
- src/data_structure.py
- tests/test_parser.py

## Next Steps
None (completed)
```

## Workflow

### Starting a Session
1. Claude checks registry for recent sessions
2. If continuing work, resume existing session
3. If new work, add entry to registry

### During a Session
1. Update registry `updated` timestamp periodically
2. Update summary file with key decisions and changes

### Ending a Session
1. Update status in registry (`completed`, `paused`, etc.)
2. Finalize summary with outcomes and next steps

## Status Values

| Status | Meaning |
|--------|---------|
| `active` | Currently being worked on |
| `completed` | Work finished, goals achieved |
| `paused` | Intentionally stopped, will resume |
| `abandoned` | Stopped without completion, no plans to resume |

**Note**: Multiple sessions can be `active` simultaneously (e.g., parallel workstreams). A session should only modify its own registry entry - never change other sessions' statuses unless explicitly directed by the user.

## Session Identity Across Compacts

A session remains the same session even when compacted via `/compact`. Compaction preserves context continuity - it's the same logical work stream, just with summarized history.

When to create a new session vs. continue existing:
- **Same session**: Continuing related work, even across compacts
- **New session**: Starting unrelated work with different goals

---

## Deep Memory

The session registry tracks *what happened* at a high level. Deep Memory provides full-text search into the raw conversation transcripts — Claude's reasoning, user messages, tool calls, and everything in between.

### How It Works

Claude Code stores conversation history as JSONL files at `~/.claude/projects/<project-slug>/*.jsonl`, one file per session. Each line is a JSON object representing one conversational entry. The `remember_conversation.py` script parses these files and provides search and navigation.

### Data Model

Each entry contains a `message.content` field with a list of typed **blocks**:

| Block Type | Description | Example |
|------------|-------------|---------|
| `thinking` | Claude's internal reasoning (not shown during session) | Design trade-offs, architecture analysis |
| `text` | Visible response (assistant) or typed message (user) | Answers, questions, code snippets |
| `tool_use` | A tool call with its input | `[Read] /path/to/file.py` |
| `tool_result` | Output from a tool call | File contents, command output |

Each JSONL entry has exactly one block type. The script classifies entries into unified **message types** that combine the raw role and block type:

| Message Type | Description |
|--------------|-------------|
| `user` | Actual human-typed messages |
| `assistant` | Claude's visible text responses |
| `thinking` | Claude's internal reasoning (not shown during session) |
| `tool_use` | Claude calling a tool (Read, Bash, Edit, etc.) |
| `tool_result` | Tool output fed back to Claude (file contents, command output) |
| `bash` | User's terminal commands and their output (`<bash-input>`, `<bash-stdout/stderr>`) |
| `slash` | Slash command invocations and output (`/rename`, `/get-session-id`, etc.) |
| `boilerplate` | System-injected caveats (e.g., "DO NOT respond to these messages") |

### Usage

```bash
# Search for a past discussion
python remember_conversation.py search "ContentTree"

# Only Claude's reasoning
python remember_conversation.py search "database" --thinking-only

# Only your messages, with date range
python remember_conversation.py search "architecture" -t user --since 2026-02-01

# Only human + Claude visible text (skip tool calls, results, reasoning)
python remember_conversation.py search "database" -t user,assistant

# Include Claude's reasoning too
python remember_conversation.py search "database" -t user,assistant,thinking

# Show entry UUIDs for use with the context command
python remember_conversation.py search "ContentTree" --show-id --head 3

# Navigate around a specific message (by UUID)
python remember_conversation.py context <uuid> -B 5 -t user

# Narrow search to one session (faster)
python remember_conversation.py search "ContentTree" --session 3c3555ee

# Search a different project's sessions
python remember_conversation.py search "sqlite" --project-dir /home/user/other-project

# Include subagent transcripts (plan agents, explore agents, etc.)
python remember_conversation.py search "sqlite-vec" --subagents all

# Search only plan subagents, exclude main session
python remember_conversation.py search "architecture" --subagents only,plan

# List sessions
python remember_conversation.py sessions
```

### Key Flags

**search command:**

| Flag | Purpose |
|------|---------|
| `-B N` / `-A N` | Show N entries before/after each match (grep-style context) |
| `--head N` / `--tail N` | Limit to first/last N results |
| `--since` / `--until` | Date range filtering (YYYY-MM-DD) |
| `--session ID` | Filter to one session (prefix match, much faster) |
| `-t TYPES` / `--message-types` | Filter by message type(s), comma-separated: `user`, `assistant`, `thinking`, `tool_use`, `tool_result`, `bash`, `slash`, `boilerplate` |
| `--thinking-only` | Only search thinking blocks |
| `--include-tools` | Also search tool_use and tool_result content |
| `--show-id` | Show entry UUIDs (for use with `context` command) |
| `--full-context` | Show full text of -B/-A context entries |
| `-i` | Case-insensitive search |
| `-p` / `--project-dir` | Search a different project's sessions |
| `-s` / `--subagents` | Include subagent transcripts (see below) |

**context command:**

| Flag | Purpose |
|------|---------|
| `-B N` / `-A N` | Show N entries before/after the target |
| `-t TYPES` / `--message-types` | Filter context entries by type (e.g., `-B 10 -t user` = 10 preceding user messages) |
| `--session ID` | Narrow the UUID search to one session (faster) |
| `--full/--brief` | Show full text (default) or one-line previews |
| `-p` / `--project-dir` | Search a different project's sessions |
| `-s` / `--subagents` | Include subagent transcripts (see below) |

### Subagent Search

By default, searches only scan main session transcripts. The `--subagents` flag includes subagent (Task tool) transcripts as well. Subagents are auto-classified by type based on filename patterns and prompt heuristics.

**Agent types:** `plan`, `explore`, `general`, `compact`, `prompt_suggestion`, `warmup`

**Flag values:**

| Value | Main session | Subagents |
|-------|-------------|-----------|
| *(not set)* | yes | none |
| `all` | yes | all types |
| `only` | no | all types |
| `plan` | yes | plan only |
| `only,plan` | no | plan only |
| `explore,plan` | yes | explore + plan |
| `only,explore` | no | explore only |

### Performance

Searching all sessions scans every JSONL file. Using `--session` to target a single file is significantly faster. Use `--session` when you already know which session contains what you're looking for.
