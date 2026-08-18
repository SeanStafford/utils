---
description: Update current session's timestamp and optionally status in registry
allowed-tools: Bash(~/.claude/scripts/print_session_marker.sh:*), Bash(sleep:*), Bash(~/.claude/scripts/find_session_marker.sh:*), Bash(python ~/.claude/scripts/update_session.py:*)
---

Update the current session's timestamp in the registry, and optionally change its status.

**Instructions:**
1. Run `~/.claude/scripts/print_session_marker.sh` to generate and print a marker
2. Observe the marker output from step 1
3. Run `sleep 1 && ~/.claude/scripts/find_session_marker.sh "<marker>"` using the exact marker string to get the session ID
4. Ask the user if they want to update the status (if not specified in the command)
5. Run `python ~/.claude/scripts/update_session.py "<session_id>" [status]`
   - If no status change needed, omit the status argument
   - Valid statuses: `active`, `completed`, `paused`, `abandoned`

**Usage examples:**
- `/update-session-timestamp` - Just update timestamp
- `/update-session-timestamp active` - Update timestamp and set status to active
