#!/usr/bin/env python3
"""List all sessions from registry."""

import csv
import sys
from pathlib import Path

# Sessions directory structure
SESSIONS_DIR = Path(".claude") / "sessions"
REGISTRY_FILENAME = "registry.csv"


def list_sessions(sessions_dir: Path, status_filter: str = None) -> None:
    """List sessions from registry, optionally filtered by status."""

    registry_path = sessions_dir / REGISTRY_FILENAME

    if not registry_path.exists():
        print(f"✗ Session registry not found at {registry_path}")
        sys.exit(1)

    try:
        with open(registry_path, "r") as f:
            reader = csv.DictReader(f)

            sessions = []
            for row in reader:
                # Filter by status if specified
                if status_filter and row["status"] != status_filter:
                    continue
                sessions.append(row)

            if not sessions:
                if status_filter:
                    print(f"No sessions with status '{status_filter}'")
                else:
                    print("No sessions found")
                sys.exit(0)

            # Print sessions
            for row in sessions:
                print(f"{row['session_id']}\t{row['name']}")

    except Exception as e:
        print(f"✗ Error reading registry: {e}")
        sys.exit(1)


if __name__ == "__main__":
    status_filter = None
    project_dir = Path.cwd()

    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--status", "-s"] and len(sys.argv) > 2:
            status_filter = sys.argv[2]
            if len(sys.argv) > 3:
                project_dir = Path(sys.argv[3])
        else:
            project_dir = Path(sys.argv[1])

    sessions_dir = project_dir / SESSIONS_DIR

    list_sessions(sessions_dir, status_filter)
