#!/usr/bin/env bash
# Find which session contains a specific marker
# Usage: find_session_marker.sh <marker> [project_dir]
# Returns: Session ID (UUID)
# Exit codes: 0=found, 1=not found, 2=multiple matches, 3=usage error

set -euo pipefail

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <marker> [project_dir]" >&2
    exit 3
fi

marker="$1"
project_dir="${2:-$PWD}"

# Convert project directory to Claude's format
# /home/__USERNAME__/myproject -> -home-__USERNAME__-myproject
claude_project_dir=$(echo "$project_dir" | tr '/' '-')
sessions_dir="$HOME/.claude/projects/${claude_project_dir}"

# Check if sessions directory exists
if [ ! -d "$sessions_dir" ]; then
    echo "Error: Sessions directory not found: $sessions_dir" >&2
    exit 1
fi

# Find files containing the marker
matches=$(grep -l "$marker" "${sessions_dir}"/*.jsonl 2>/dev/null || true)

# Handle results
if [ -z "$matches" ]; then
    echo "Error: Marker not found in any session" >&2
    exit 1
fi

# Count matches
match_count=$(echo "$matches" | wc -l)

if [ "$match_count" -gt 1 ]; then
    echo "Error: Marker found in multiple sessions:" >&2
    echo "$matches" | xargs -n1 basename -s .jsonl >&2
    exit 2
fi

# Extract session ID from filename
session_id=$(basename "$matches" .jsonl)
echo "$session_id"
