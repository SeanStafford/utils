#!/usr/bin/env bash
# Print a unique session marker for identification
# Format: CLAUDE_SESSION_MARKER_<timestamp>_<random3char>

# Generate ISO 8601 timestamp
timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Generate 3-character random string (alphanumeric lowercase)
random_str=$(tr -dc 'a-z0-9' < /dev/urandom | head -c 3)

# Print marker to stdout
echo "CLAUDE_SESSION_MARKER_${timestamp}_${random_str}"

