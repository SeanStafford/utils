---
description: Display the current session's name from the registry
allowed-tools: Bash(~/.claude/scripts/print_session_marker.sh:*), Bash(sleep:*), Bash(~/.claude/scripts/find_session_marker.sh:*), Bash(python ~/.claude/scripts/lookup_session_name.py:*)
---

Identify the current session and look up its name in the session registry.

**Instructions:**
1. Run `~/.claude/scripts/print_session_marker.sh` to generate and print a marker
2. Observe the marker output from step 1
3. Run `sleep 1 && ~/.claude/scripts/find_session_marker.sh "<marker>"` using the exact marker string to get the session ID
4. Run `python ~/.claude/scripts/lookup_session_name.py "<session_id>"` to look up and display the session details
