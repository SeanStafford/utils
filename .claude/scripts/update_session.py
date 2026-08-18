#!/usr/bin/env python3
"""Update session timestamp and optionally status in registry."""

import csv
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Sessions directory structure
SESSIONS_DIR = Path(".claude") / "sessions"
REGISTRY_FILENAME = "registry.csv"

EXPECTED_COLUMNS = {"session_id", "name", "status", "created", "updated", "description"}


def update_session(session_id: str, sessions_dir: Path, new_status: str = None) -> None:
    """Update session timestamp and optionally status."""

    registry_path = sessions_dir / REGISTRY_FILENAME

    if not registry_path.exists():
        print(f"✗ Session registry not found at {registry_path}")
        sys.exit(1)

    # Get current timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M")

    # Read and validate CSV
    rows = []
    session_found = False
    fieldnames = None
    old_status = None
    session_name = None

    try:
        with open(registry_path, "r") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Validate that we have the expected columns
            if set(fieldnames) != EXPECTED_COLUMNS:
                print("✗ Registry has incorrect columns")
                print(f"  Expected: {EXPECTED_COLUMNS}")
                print(f"  Found: {set(fieldnames)}")
                sys.exit(1)

            for line_num, row in enumerate(
                reader, start=2
            ):  # start=2 because row 1 is header
                # Check for None keys (indicates unquoted commas or malformed CSV)
                none_keys = [k for k in row.keys() if k is None]
                if none_keys:
                    print("✗ Malformed CSV detected at line {line_num}")
                    print(
                        "  The CSV contains unquoted commas or other formatting issues"
                    )
                    print("  Please fix the CSV manually before using this script")
                    print("  Tip: Ensure all fields with commas are properly quoted")
                    sys.exit(1)

                # Check for extra columns (CSV read more fields than header)
                if len(row) > len(fieldnames):
                    print(f"✗ Malformed CSV detected at line {line_num}")
                    print("  Row has more fields than header columns")
                    print("  This usually means unquoted commas in a field")
                    sys.exit(1)

                if row["session_id"] == session_id:
                    session_found = True
                    session_name = row["name"]
                    # Update timestamp
                    row["updated"] = timestamp
                    # Update status if provided
                    if new_status:
                        old_status = row["status"]
                        row["status"] = new_status
                rows.append(row)
    except Exception as e:
        print(f"✗ Error reading registry: {e}")
        sys.exit(1)

    if not session_found:
        print(f"✗ Session {session_id} not found in registry")
        sys.exit(1)

    # Write back atomically with proper quoting
    temp_fd = None
    temp_path = None
    try:
        # Create temp file in same directory as registry
        temp_fd, temp_path = tempfile.mkstemp(dir=sessions_dir, suffix=".tmp", text=True)

        # Write to temp file
        with os.fdopen(temp_fd, "w", newline="") as f:
            temp_fd = None  # fdopen takes ownership, don't close again
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC
            )
            writer.writeheader()
            writer.writerows(rows)

        # Atomic replace (only replaces if write succeeded)
        os.replace(temp_path, registry_path)
        temp_path = None  # Successfully replaced, don't delete

        # Only print success AFTER successful atomic write
        if new_status:
            print(f"✓ Updated session '{session_name}'")
            print(f"  Status: {old_status} → {new_status}")
        else:
            print(f"✓ Updated session '{session_name}'")
        print(f"  Timestamp: {timestamp}")
    except Exception as e:
        print(f"✗ Error writing registry: {e}")
        sys.exit(1)
    finally:
        # Clean up temp file if it still exists (error occurred before replace)
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except:
                pass
        if temp_path is not None and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: update_session.py <session_id> [status] [project_dir]",
            file=sys.stderr,
        )
        sys.exit(1)

    session_id = sys.argv[1]
    new_status = (
        sys.argv[2] if len(sys.argv) >= 3 and sys.argv[2] not in [".", ""] else None
    )
    project_dir = Path(sys.argv[3]) if len(sys.argv) >= 4 else Path.cwd()

    sessions_dir = project_dir / SESSIONS_DIR

    update_session(session_id, sessions_dir, new_status)
