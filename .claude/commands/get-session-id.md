---
description: Display the current session's internal ID
allowed-tools: Bash(~/.claude/scripts/print_session_marker.sh:*), Bash(sleep:*), Bash(~/.claude/scripts/find_session_marker.sh:*)
---

Identify the current Claude Code session ID by injecting a unique marker and searching for it.

**Instructions:**
1. Run `~/.claude/scripts/print_session_marker.sh` to generate and print a marker
2. Observe the marker output from step 1
3. Run `sleep 1 && ~/.claude/scripts/find_session_marker.sh "<marker>"` using the exact marker string from step 2
4. Display the session ID to the user
