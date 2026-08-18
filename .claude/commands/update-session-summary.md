---
description: Update session summary file and timestamp in registry
allowed-tools: Bash(~/.claude/scripts/print_session_marker.sh:*), Bash(sleep:*), Bash(~/.claude/scripts/find_session_marker.sh:*), Bash(python ~/.claude/scripts/update_session.py:*), Read, Edit
---

Update the session summary file with current progress, then update the timestamp (and optionally status) in the registry.

**Arguments:** `$ARGUMENTS` (optional status: `active`, `completed`, `paused`, `abandoned`)

**Reference:** See `docs/SESSION_MANAGEMENT.md` for the session summary file format if needed.

**Instructions:**

**Part 1: Update session summary file**
1. Determine the session name from the registry (use `/get-session-name` logic or check `.claude/sessions/registry.csv`)
2. Read the summary file at `.claude/sessions/{name}.md`
3. Update it to reflect current progress:
   - Update **Status** in the header to match the new status (if changing)
   - Update **Last Updated** timestamp
   - Add any new key decisions, files modified, or outcomes from this conversation
   - Update **Next Steps** to reflect what remains
4. Do NOT rewrite the whole file — preserve existing content and append/update incrementally

**Part 2: Update registry timestamp**
5. Run `~/.claude/scripts/print_session_marker.sh` to generate a marker
6. Run `sleep 1 && ~/.claude/scripts/find_session_marker.sh "<marker>"` to get session ID
7. Run `python ~/.claude/scripts/update_session.py "<session_id>" [status]`
   - Pass through the status from `$ARGUMENTS` if provided
   - If no status specified, omit the status argument (timestamp-only update)
