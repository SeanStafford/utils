#!/usr/bin/env python
"""
Search Claude Code conversation transcripts.

Searches JSONL session files for past discussions, design decisions,
and reasoning. Useful for recovering context from previous sessions.

Data Model
----------
Claude Code stores conversation history as JSONL files, one per session,
at ~/.claude/projects/<project-slug>/*.jsonl. Each line is a JSON object
representing one conversational "entry" — a single user message, assistant
response, or system event.

Each entry's message.content field contains a list of typed "blocks":

  - thinking:    Claude's internal reasoning (not shown to user during session)
  - text:        Actual response text (assistant) or typed message (user)
  - tool_use:    A tool call (Read, Bash, Edit, etc.) with its input
  - tool_result: The output from a tool call, fed back as a "user" entry

Message Types
-------------
The raw JSONL marks every entry as either "user" or "assistant", but each
entry contains exactly one block type. This script classifies entries into
unified message types that combine role and block type:

  - user:          Actual human-typed messages
  - assistant:     Claude's visible text responses
  - thinking:      Claude's internal reasoning (not shown during session)
  - tool_use:      Claude calling a tool (Read, Bash, Edit, etc.)
  - tool_result:   Tool output fed back to Claude (file contents, command output)
  - bash:          User's terminal commands and their output (<bash-input>, <bash-stdout/stderr>)
  - slash:         Slash command invocations and output (/rename, /get-session-id, etc.)
  - boilerplate:   System-injected caveats (e.g., "DO NOT respond to these messages")

Commands
--------
  search   Regex search across transcripts with filtering and context
  context  Show a specific message by UUID with surrounding conversation
  sessions List available session files

Usage:
    python scripts/remember_conversation.py search "ContentTree"
    python scripts/remember_conversation.py search "leaf.*class" --thinking-only
    python scripts/remember_conversation.py search "database" --since 2026-02-01 -A 1
    python scripts/remember_conversation.py search "ContentTree" --show-id
    python scripts/remember_conversation.py context <uuid> -B 5 -t user
    python scripts/remember_conversation.py sessions
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer


def get_sessions_dir(project_dir: Optional[str] = None) -> Path:
    """Derive the Claude Code sessions directory for a project.

    Claude Code stores sessions at ~/.claude/projects/<slug>/*.jsonl
    where <slug> is the absolute project path with '/' replaced by '-'.
    E.g. /home/user/myproject -> -home-user-myproject
    """
    project_path = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    slug = str(project_path).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


SESSIONS_DIR = get_sessions_dir()

app = typer.Typer(
    help="Search Claude Code conversation transcripts.",
    invoke_without_command=True,
)


@app.callback()
def main(ctx: typer.Context):
    """Show help by default when no command is provided."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


# ---------------------------------------------------------------------------
# File gathering
# ---------------------------------------------------------------------------


AGENT_TYPES = {"plan", "explore", "general", "compact", "prompt_suggestion", "warmup"}


def classify_subagent(path: Path) -> str:
    """
    Classify a subagent JSONL file by type based on filename and first prompt.

    Returns one of: compact, explore, plan, prompt_suggestion, warmup, general.
    """
    # Filename-based detection
    if "compact" in path.name:
        return "compact"
    if "prompt_suggestion" in path.name:
        return "prompt_suggestion"

    # Prompt-based detection
    try:
        with open(path) as f:
            first_line = f.readline().strip()
            if not first_line:
                return "general"
            d = json.loads(first_line)
            msg = d.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        content = b.get("text", "")
                        break
                else:
                    return "general"
            if content.startswith("Thoroughness:"):
                return "explore"
            if content.startswith("Design"):
                return "plan"
            if content.startswith("Warmup") or content.startswith("I'll help you warm up"):
                return "warmup"
            # Heuristic: exploration prompts typically start with investigative verbs
            explore_starts = (
                "Explore ",
                "Find ",
                "Read and analyze",
                "I need to understand",
                "Thoroughly ",
            )
            if any(content.startswith(s) for s in explore_starts):
                return "explore"
    except (json.JSONDecodeError, IOError):
        pass

    return "general"


def gather_jsonl_files(
    session: Optional[str] = None, subagents: Optional[str] = None
) -> List[Path]:
    """
    Collect JSONL session files with subagent filtering.

    Args:
        session: Filter to sessions matching this prefix.
        subagents: Subagent inclusion mode. None means no subagents.
            'all' includes main + all subagents.
            'only' includes all subagents, excludes main.
            Comma-separated types (plan,explore,general,compact) include main + those types.
            Prefix with 'only,' to exclude main (e.g. 'only,plan').
    """
    if not SESSIONS_DIR.exists():
        return []

    # Parse subagents flag
    include_main = True
    type_filter = None

    if subagents is not None:
        parts = {p.strip() for p in subagents.split(",")}
        if "only" in parts:
            include_main = False
            parts.discard("only")
        if parts and parts != {"all"}:
            type_filter = parts & AGENT_TYPES

    # Main session files
    main_files = list(SESSIONS_DIR.glob("*.jsonl"))
    if session:
        main_files = [f for f in main_files if f.stem.startswith(session)]

    files = list(main_files) if include_main else []

    # Subagent files
    if subagents is not None:
        subagent_files = []
        if session:
            for main_file in main_files:
                subagent_dir = SESSIONS_DIR / main_file.stem / "subagents"
                if subagent_dir.exists():
                    subagent_files.extend(subagent_dir.glob("*.jsonl"))
        else:
            subagent_files = list(SESSIONS_DIR.glob("*/subagents/*.jsonl"))

        # Filter by agent type if specified
        if type_filter:
            subagent_files = [f for f in subagent_files if classify_subagent(f) in type_filter]

        files.extend(subagent_files)

    return sorted(files, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------


def parse_entry(raw: dict) -> Optional[dict]:
    """
    Extract semantically meaningful fields from a JSONL entry.

    Each raw JSONL entry has metadata (uuid, timestamp, sessionId, slug) and a
    message with a content field. Content is either a string (for command
    invocations) or a list of typed blocks (thinking, text, tool_use, tool_result).

    This function flattens the content into a uniform list of {type, text} dicts
    called "blocks", and sub-classifies the role (see module docstring for roles).

    Returns None if entry has no searchable content (e.g., summary entries).
    """
    msg = raw.get("message", {})
    content_blocks = msg.get("content", [])
    timestamp = raw.get("timestamp", "")
    role = raw.get("type", msg.get("role", "unknown"))
    uuid = raw.get("uuid", "")
    session_id = raw.get("sessionId", "")
    slug = raw.get("slug", "")

    # Detect system-generated user entries from string content
    if isinstance(content_blocks, str):
        if (
            "<bash-input>" in content_blocks
            or "<bash-stdout>" in content_blocks
            or "<bash-stderr>" in content_blocks
        ):
            role = "bash"
        elif "<command-name>" in content_blocks or "<local-command-stdout>" in content_blocks:
            role = "slash"
        elif "<local-command-caveat>" in content_blocks:
            role = "boilerplate"
        content_blocks = [{"type": "text", "text": content_blocks}]

    # Extract content by type
    blocks = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "")

        if block_type == "thinking":
            blocks.append({"type": "thinking", "text": block.get("thinking", "")})

        elif block_type == "text":
            blocks.append({"type": "text", "text": block.get("text", "")})

        elif block_type == "tool_use":
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            # Summarize tool use
            summary = f"[{tool_name}]"
            if isinstance(tool_input, dict):
                if "file_path" in tool_input:
                    summary += f" {tool_input['file_path']}"
                elif "command" in tool_input:
                    cmd = tool_input["command"][:120]
                    summary += f" {cmd}"
                elif "pattern" in tool_input:
                    summary += f" pattern={tool_input['pattern']}"
            blocks.append({"type": "tool_use", "text": summary})

        elif block_type == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, str):
                blocks.append({"type": "tool_result", "text": result_content})
            elif isinstance(result_content, list):
                for item in result_content:
                    if isinstance(item, dict) and "text" in item:
                        blocks.append({"type": "tool_result", "text": item["text"]})

    if not blocks:
        return None

    # Classify into unified message type
    # Each JSONL entry has exactly one block type, so we use it directly
    block_types = {b["type"] for b in blocks}

    if role in ("bash", "slash", "boilerplate"):
        message_type = role
    elif role == "user" and block_types == {"tool_result"}:
        message_type = "tool_result"
    elif role == "user":
        message_type = "user"
    elif role == "assistant" and block_types == {"thinking"}:
        message_type = "thinking"
    elif role == "assistant" and block_types == {"tool_use"}:
        message_type = "tool_use"
    elif role == "assistant":
        message_type = "assistant"
    else:
        message_type = role

    return {
        "timestamp": timestamp,
        "message_type": message_type,
        "uuid": uuid,
        "session_id": session_id,
        "slug": slug,
        "blocks": blocks,
    }


def format_timestamp(ts: str) -> str:
    """Format ISO timestamp to readable short form."""
    if not ts:
        return "????"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts[:16]


def parse_date(date_str: str) -> datetime:
    """Parse a date string (YYYY-MM-DD or YYYY-MM-DD HH:MM)."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise typer.BadParameter(f"Cannot parse date: {date_str}. Use YYYY-MM-DD format.")


def entry_timestamp(entry: dict) -> Optional[datetime]:
    """Extract datetime from parsed entry."""
    ts = entry.get("timestamp", "")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------


def matches_entry(
    entry: dict,
    pattern: re.Pattern,
    search_types: set,
) -> List[dict]:
    """
    Check if entry matches pattern. Returns list of matching blocks with context.
    """
    hits = []
    for block in entry["blocks"]:
        if block["type"] not in search_types:
            continue
        if pattern.search(block["text"]):
            hits.append(block)
    return hits


def format_match(
    entry: dict,
    hits: List[dict],
    show_slug: bool,
    show_id: bool,
    context_lines: int,
    show_session: bool = False,
) -> str:
    """Format a matching entry for display."""
    parts = []

    # Header line
    ts = format_timestamp(entry["timestamp"])
    role = entry["message_type"]
    header = f"[{ts}] {role}"
    if show_session and entry.get("session_id"):
        header += f" [{entry['session_id']}]"
    if show_slug:
        header += f" ({entry['slug']})"
    if show_id and entry.get("uuid"):
        header += f" {entry['uuid']}"
    parts.append(typer.style(header, fg=typer.colors.CYAN, bold=True))

    # Matching blocks
    for hit in hits:
        block_type = hit["type"]
        text = hit["text"]

        type_color = {
            "thinking": typer.colors.YELLOW,
            "text": typer.colors.WHITE,
            "tool_use": typer.colors.MAGENTA,
            "tool_result": typer.colors.GREEN,
        }.get(block_type, typer.colors.WHITE)

        type_label = typer.style(f"  ({block_type})", fg=type_color)
        parts.append(type_label)

        # Show text with line limit
        lines = text.split("\n")
        if context_lines > 0 and len(lines) > context_lines * 2:
            # Find the matching lines and show context around them
            shown = set()
            for i, line in enumerate(lines):
                if pattern.search(line) if hasattr(pattern, "search") else False:
                    for j in range(
                        max(0, i - context_lines), min(len(lines), i + context_lines + 1)
                    ):
                        shown.add(j)

            if shown:
                for i in sorted(shown):
                    parts.append(f"    {lines[i]}")
                if max(shown) < len(lines) - 1:
                    parts.append(f"    ... ({len(lines) - len(shown)} more lines)")
            else:
                # Pattern matched across lines or in a way we can't isolate
                for line in lines[: context_lines * 2]:
                    parts.append(f"    {line}")
                parts.append(f"    ... ({len(lines) - context_lines * 2} more lines)")
        else:
            for line in lines[:40]:
                parts.append(f"    {line}")
            if len(lines) > 40:
                parts.append(f"    ... ({len(lines) - 40} more lines)")

    return "\n".join(parts)


def format_context_entry(
    entry: dict,
    show_slug: bool,
    show_id: bool = False,
    full: bool = False,
    show_session: bool = False,
) -> str:
    """Format a non-matching context entry (for -B/-A display)."""
    ts = format_timestamp(entry["timestamp"])
    role = entry["message_type"]
    header = f"[{ts}] {role}"
    if show_session and entry.get("session_id"):
        header += f" [{entry['session_id']}]"
    if show_slug:
        header += f" ({entry['slug']})"
    if show_id and entry.get("uuid"):
        header += f" {entry['uuid']}"

    parts = [typer.style(header, fg=typer.colors.BRIGHT_BLACK)]

    for block in entry["blocks"]:
        text = block["text"]
        if full:
            parts.append(f"  ({block['type']})")
            for line in text.split("\n")[:80]:
                parts.append(f"    {line}")
            lines = text.split("\n")
            if len(lines) > 80:
                parts.append(f"    ... ({len(lines) - 80} more lines)")
        else:
            lines = text.split("\n")
            preview = lines[0][:100] if lines else ""
            if len(lines) > 1:
                preview += f" ... ({len(lines)} lines)"
            parts.append(f"  ({block['type']}) {preview}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

# Store pattern at module level so format_match can use it for line highlighting
pattern = None


@app.command()
def search(
    query: str = typer.Argument(..., help="Perl-compatible regex pattern"),
    before: int = typer.Option(0, "-B", help="Show N entries before each match"),
    after: int = typer.Option(0, "-A", help="Show N entries after each match"),
    head: Optional[int] = typer.Option(None, "--head", help="Show only first N matches"),
    tail: Optional[int] = typer.Option(None, "--tail", help="Show only last N matches"),
    since: Optional[str] = typer.Option(
        None, "--since", help="Only entries after this date (YYYY-MM-DD)"
    ),
    until: Optional[str] = typer.Option(
        None, "--until", help="Only entries before this date (YYYY-MM-DD)"
    ),
    session: Optional[str] = typer.Option(
        None, "--session", help="Filter to specific session ID (prefix match)"
    ),
    thinking_only: bool = typer.Option(
        False, "--thinking-only", help="Only search thinking blocks"
    ),
    include_tools: bool = typer.Option(
        False, "--include-tools", help="Also search tool_use and tool_result"
    ),
    show_slug: bool = typer.Option(False, "--show-slug", help="Show session slug in output"),
    show_id: bool = typer.Option(False, "--show-id", help="Show entry UUID in output"),
    show_session: bool = typer.Option(
        False, "--show-session", help="Show session ID prefix in output"
    ),
    message_types: Optional[str] = typer.Option(
        None,
        "--message-types",
        "-t",
        help="Filter by message type(s), comma-separated (e.g. user,assistant,thinking)",
    ),
    ignore_case: bool = typer.Option(False, "-i", help="Case-insensitive search"),
    full_context: bool = typer.Option(
        False, "--full-context", help="Show full text of -B/-A context entries"
    ),
    context_lines: int = typer.Option(
        5, "--context-lines", help="Lines of text context around match within a block"
    ),
    subagents: Optional[str] = typer.Option(
        None,
        "--subagents",
        "-s",
        help="Include subagent transcripts: 'all', 'only', or comma-separated types (plan,explore,general,compact). Prefix with 'only,' to exclude main session.",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-p", help="Project directory (default: cwd)"
    ),
):
    """Search conversation transcripts with regex."""
    global pattern, SESSIONS_DIR

    if project_dir:
        SESSIONS_DIR = get_sessions_dir(project_dir)

    # Compile regex
    flags = re.IGNORECASE if ignore_case else 0
    try:
        pattern = re.compile(query, flags)
    except re.error as e:
        typer.secho(f"Invalid regex: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Parse date filters
    since_dt = parse_date(since) if since else None
    until_dt = parse_date(until) if until else None

    # Determine which content types to search
    search_types = set()
    if thinking_only:
        search_types = {"thinking"}
    else:
        search_types = {"thinking", "text"}
        if include_tools:
            search_types.update({"tool_use", "tool_result"})

    # Find session files
    jsonl_files = gather_jsonl_files(session=session, subagents=subagents)
    if not jsonl_files:
        msg = f"No sessions matching: {session}" if session else "Sessions directory not found"
        typer.secho(msg, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Collect all matching entries with context
    all_results = []  # List of (entry, hits, file_entries_for_context, entry_index)

    for jsonl_path in jsonl_files:
        # Parse all entries in file
        entries = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                parsed = parse_entry(raw)
                if parsed:
                    entries.append(parsed)

        # Search entries
        for i, entry in enumerate(entries):
            # Date filtering
            if since_dt or until_dt:
                ts = entry_timestamp(entry)
                if ts:
                    if since_dt and ts < since_dt:
                        continue
                    if until_dt and ts > until_dt:
                        continue

            # Role filtering
            if message_types:
                allowed = {t.strip() for t in message_types.split(",")}
                if entry["message_type"] not in allowed:
                    continue

            hits = matches_entry(entry, pattern, search_types)
            if hits:
                all_results.append((entry, hits, entries, i))

    if not all_results:
        typer.secho("No matches found.", fg=typer.colors.YELLOW)
        raise typer.Exit()

    if tail:
        all_results = all_results[-tail:]
    if head:
        all_results = all_results[:head]

    # Display results
    for result_idx, (entry, hits, entries, i) in enumerate(all_results):
        if result_idx > 0:
            typer.echo(typer.style("─" * 72, fg=typer.colors.BRIGHT_BLACK))

        # Before context
        if before > 0:
            start = max(0, i - before)
            for j in range(start, i):
                typer.echo(
                    format_context_entry(
                        entries[j], show_slug, show_id, full=full_context, show_session=show_session
                    )
                )

        # The match itself
        typer.echo(
            format_match(entry, hits, show_slug, show_id, context_lines, show_session=show_session)
        )

        # After context
        if after > 0:
            end = min(len(entries), i + after + 1)
            for j in range(i + 1, end):
                typer.echo(
                    format_context_entry(
                        entries[j], show_slug, show_id, full=full_context, show_session=show_session
                    )
                )

    typer.echo()
    typer.secho(f"{len(all_results)} match(es)", fg=typer.colors.BRIGHT_BLACK)


@app.command()
def context(
    uuid: str = typer.Argument(..., help="UUID of the target message"),
    before: int = typer.Option(0, "-B", help="Show N entries before the target"),
    after: int = typer.Option(0, "-A", help="Show N entries after the target"),
    message_types: Optional[str] = typer.Option(
        None,
        "--message-types",
        "-t",
        help="Filter context to message type(s), comma-separated (e.g. user,assistant)",
    ),
    session: Optional[str] = typer.Option(
        None, "--session", help="Session ID to search (prefix match, speeds up lookup)"
    ),
    full: bool = typer.Option(True, "--full/--brief", help="Show full text (default) or brief"),
    show_slug: bool = typer.Option(False, "--show-slug", help="Show session slug in output"),
    show_id: bool = typer.Option(False, "--show-id", help="Show entry UUID in output"),
    show_session: bool = typer.Option(
        False, "--show-session", help="Show session ID prefix in output"
    ),
    subagents: Optional[str] = typer.Option(
        None,
        "--subagents",
        "-s",
        help="Include subagent transcripts: 'all', 'only', or comma-separated types (plan,explore,general,compact). Prefix with 'only,' to exclude main session.",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-p", help="Project directory (default: cwd)"
    ),
):
    """
    Show a message by UUID with surrounding context.

    Use `search --show-id` to find UUIDs, then use this command to explore
    the conversation around a specific message.

    Examples:
        context abc123 -B 5 -t user         # 5 user messages before abc123
        context abc123 -A 3                # 3 entries after abc123
        context abc123 -B 2 -A 2           # 2 before, 2 after
    """
    global SESSIONS_DIR

    if project_dir:
        SESSIONS_DIR = get_sessions_dir(project_dir)

    # Search session files for the UUID
    target_entry = None
    target_index = None
    all_entries = None

    jsonl_files = gather_jsonl_files(session=session, subagents=subagents)
    if not jsonl_files:
        msg = f"No sessions matching: {session}" if session else "Sessions directory not found"
        typer.secho(msg, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    for jsonl_path in jsonl_files:
        entries = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                parsed = parse_entry(raw)
                if parsed:
                    entries.append(parsed)

        # Check for UUID match (prefix match for convenience)
        for i, entry in enumerate(entries):
            if entry.get("uuid", "").startswith(uuid):
                target_entry = entry
                target_index = i
                all_entries = entries
                break

        if target_entry:
            break

    if not target_entry:
        typer.secho(f"UUID not found: {uuid}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Collect context entries with optional message type filtering
    allowed = {t.strip() for t in message_types.split(",")} if message_types else None
    display_entries = []

    # Before context
    if before > 0:
        collected = []
        j = target_index - 1
        while j >= 0 and len(collected) < before:
            if allowed is None or all_entries[j]["message_type"] in allowed:
                collected.append(all_entries[j])
            j -= 1
        # Reverse so they're in chronological order
        display_entries.extend(reversed(collected))

    # The target itself
    display_entries.append(target_entry)

    # After context
    if after > 0:
        collected = []
        j = target_index + 1
        while j < len(all_entries) and len(collected) < after:
            if allowed is None or all_entries[j]["message_type"] in allowed:
                collected.append(all_entries[j])
            j += 1
        display_entries.extend(collected)

    # Display
    for i, entry in enumerate(display_entries):
        if i > 0:
            typer.echo(typer.style("─" * 72, fg=typer.colors.BRIGHT_BLACK))

        is_target = entry is target_entry
        if is_target:
            # Show target with full formatting
            ts = format_timestamp(entry["timestamp"])
            header = f"[{ts}] {entry['message_type']}"
            if show_session and entry.get("session_id"):
                header += f" [{entry['session_id']}]"
            if show_slug:
                header += f" ({entry['slug']})"
            if show_id:
                header += f" {entry['uuid']}"
            typer.echo(typer.style(header, fg=typer.colors.CYAN, bold=True))
            for block in entry["blocks"]:
                type_color = {
                    "thinking": typer.colors.YELLOW,
                    "text": typer.colors.WHITE,
                    "tool_use": typer.colors.MAGENTA,
                    "tool_result": typer.colors.GREEN,
                }.get(block["type"], typer.colors.WHITE)
                typer.echo(typer.style(f"  ({block['type']})", fg=type_color))
                for line in block["text"].split("\n"):
                    typer.echo(f"    {line}")
        else:
            typer.echo(
                format_context_entry(
                    entry, show_slug, show_id, full=full, show_session=show_session
                )
            )


def load_registry() -> dict:
    """Load session registry CSV, returning dict keyed by session_id."""
    registry_path = Path.cwd() / ".claude" / "sessions" / "registry.csv"
    result = {}
    if not registry_path.exists():
        return result
    try:
        import csv
        with open(registry_path, newline="") as f:
            for row in csv.DictReader(f):
                sid = row.get("session_id", "").strip('"')
                result[sid] = {
                    "name": row.get("name", "").strip('"'),
                    "description": row.get("description", "").strip('"'),
                    "status": row.get("status", "").strip('"'),
                }
    except (IOError, KeyError):
        pass
    return result


@app.command()
def sessions(
    query: Optional[str] = typer.Argument(None, help="Optional regex to count matches per session"),
    recent: int = typer.Option(10, "--recent", "-n", help="Show N most recent sessions"),
    message_types: Optional[str] = typer.Option(
        None,
        "--message-types",
        "-t",
        help="Filter by message type(s), comma-separated (e.g. user,assistant,thinking)",
    ),
    ignore_case: bool = typer.Option(False, "-i", help="Case-insensitive search"),
    all_sessions: bool = typer.Option(
        False, "--all", "-a", help="Show sessions with zero matches too"
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-p", help="Project directory (default: cwd)"
    ),
):
    """List available sessions, optionally counting matches for a query."""
    global SESSIONS_DIR

    if project_dir:
        SESSIONS_DIR = get_sessions_dir(project_dir)

    if not SESSIONS_DIR.exists():
        typer.secho(f"Sessions directory not found: {SESSIONS_DIR}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    jsonl_files = sorted(
        SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if not jsonl_files:
        typer.echo("No session files found.")
        raise typer.Exit()

    registry = load_registry()

    # No query — list sessions with name from registry
    if query is None:
        typer.secho(f"{'Modified':<12} {'Size':>8}  {'Session ID':<36}  Name", fg=typer.colors.BLUE, bold=True)
        typer.echo("─" * 80)
        for f in jsonl_files[:recent]:
            stat = f.stat()
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
            size_kb = stat.st_size / 1024
            size_str = f"{size_kb / 1024:.1f}MB" if size_kb > 1024 else f"{size_kb:.0f}KB"
            info = registry.get(f.stem, {})
            name = info.get("name", "") or "(unregistered)"
            line = f"{modified:<12} {size_str:>8}  {f.stem}  {name}"
            typer.echo(line)
        return

    # Query — compile regex and count matches per session
    flags = re.IGNORECASE if ignore_case else 0
    try:
        pat = re.compile(query, flags)
    except re.error as e:
        typer.secho(f"Invalid regex: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    allowed_types = {t.strip() for t in message_types.split(",")} if message_types else None
    search_types = {"thinking", "text"}

    results = []
    for f in jsonl_files:
        match_count = 0
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = parse_entry(raw)
                if not entry:
                    continue
                if allowed_types and entry["message_type"] not in allowed_types:
                    continue
                for block in entry["blocks"]:
                    if block["type"] in search_types and pat.search(block["text"]):
                        match_count += 1
                        break  # count per entry, not per block

        stat = f.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
        info = registry.get(f.stem, {})
        results.append((match_count, modified, f.stem, info.get("name", "") or "(unregistered)", info.get("description", "")))

    # Sort by match count descending, then by modified date descending
    results.sort(key=lambda r: (-r[0], r[1]), reverse=False)
    results.sort(key=lambda r: -r[0])

    if not all_sessions:
        results = [r for r in results if r[0] > 0]

    if not results:
        typer.secho("No matches found in any session.", fg=typer.colors.YELLOW)
        raise typer.Exit()

    typer.secho(f"{'Matches':>7}  {'Modified':<12} {'Session ID':<36}  Name", fg=typer.colors.BLUE, bold=True)
    typer.echo("─" * 80)
    for match_count, modified, session_id, name, description in results:
        count_str = f"{match_count:>7}"
        line = f"{count_str}  {modified:<12} {session_id}  {name}"
        if match_count > 0:
            typer.echo(line)
        else:
            typer.echo(typer.style(line, fg=typer.colors.BRIGHT_BLACK))

    typer.echo()
    typer.secho(f"{len(results)} session(s) with matches", fg=typer.colors.BRIGHT_BLACK)


if __name__ == "__main__":
    app()
