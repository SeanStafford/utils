#!/usr/bin/env python3
"""Look up session name and details from registry by session ID."""

import csv
import sys
from pathlib import Path

# Sessions directory structure
SESSIONS_DIR = Path(".claude") / "sessions"
REGISTRY_FILENAME = "registry.csv"


def lookup_session(session_id: str, sessions_dir: Path) -> None:
    """Look up session in registry and print details."""

    registry_path = sessions_dir / REGISTRY_FILENAME

    if not registry_path.exists():
        print(f"Warning: Session registry not found at {registry_path}")
        print("Session has no registered name")
        sys.exit(0)

    # Read CSV and search for session ID
    with open(registry_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["session_id"] == session_id:
                # Found it - print formatted output
                print("\n\u2713 Session found in registry")
                print("-" * 30)
                print(f"ID: {row['session_id']}")
                print(f"Name: {row['name']}")
                print(f"Status: {row['status']}")
                print(f"Description: {row['description']}")

                # Check if detailed summary file exists
                summary_file = sessions_dir / f"{row['name']}.md"
                if summary_file.exists():
                    print(f"Details: {SESSIONS_DIR / row['name']}.md")

                print("")
                sys.exit(0)

    # Not found
    # x symbol is U+2717
    print(f"\n\u2717 Session with id {session_id} not found in registry\n")
    sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: lookup_session_name.py <session_id> [project_dir]", file=sys.stderr
        )
        sys.exit(1)

    session_id = sys.argv[1]
    project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
    sessions_dir = project_dir / SESSIONS_DIR

    lookup_session(session_id, sessions_dir)
