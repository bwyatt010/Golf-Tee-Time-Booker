#!/usr/bin/env python3
"""
Crontab cleanup — removes all GOLF_TEE_BOT entries for schedules
that no longer exist in the database, keeping only active ones.

Run:  python3 cleanup_crontab.py [--dry-run]
"""

import sys
import os
import subprocess
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DRY_RUN = "--dry-run" in sys.argv

# Find the DB
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dashboard.db")
if not os.path.exists(DB_PATH):
    print(f"ERROR: DB not found at {DB_PATH}")
    sys.exit(1)

# Get all active schedule IDs from DB
conn = sqlite3.connect(DB_PATH)
active_ids = {row[0] for row in conn.execute("SELECT id FROM schedules WHERE enabled = 1").fetchall()}
all_ids    = {row[0] for row in conn.execute("SELECT id FROM schedules").fetchall()}
conn.close()
print(f"Active schedule IDs in DB: {sorted(active_ids)}")
print(f"All schedule IDs in DB:    {sorted(all_ids)}")

# Read crontab
result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
lines = result.stdout.splitlines()

kept    = []
removed = []

for line in lines:
    if "GOLF_TEE_BOT" not in line:
        kept.append(line)
        continue

    # Extract SCHEDULE_ID
    sid = None
    for part in line.split():
        if part.startswith("SCHEDULE_ID="):
            try:
                sid = int(part.split("=")[1])
            except ValueError:
                pass
            break

    if sid is None:
        print(f"  WARN: Could not parse SCHEDULE_ID from: {line[:80]}")
        kept.append(line)
        continue

    if sid in active_ids:
        kept.append(line)
        print(f"  KEEP  SCHEDULE_ID={sid}: {line[:80]}")
    else:
        removed.append((sid, line))
        print(f"  REMOVE SCHEDULE_ID={sid} (not in active DB): {line[:80]}")

print(f"\nSummary: keeping {len([l for l in kept if 'GOLF_TEE_BOT' in l])} bot entries, "
      f"removing {len(removed)} dead entries.")

if DRY_RUN:
    print("\n[DRY RUN] No changes made. Re-run without --dry-run to apply.")
    sys.exit(0)

if not removed:
    print("\nNothing to remove — crontab is clean.")
    sys.exit(0)

# Write cleaned crontab
content = "\n".join(kept) + "\n"
proc = subprocess.run(["crontab", "-"], input=content, capture_output=True, text=True)
if proc.returncode != 0:
    print(f"ERROR writing crontab: {proc.stderr}")
    sys.exit(1)

print(f"\n✓ Crontab updated. Removed {len(removed)} dead entries.")
print("\nCurrent GOLF_TEE_BOT entries:")
for line in kept:
    if "GOLF_TEE_BOT" in line:
        print(f"  {line}")
