# Add a dry run to cleanup.py

Before ops schedules `cleanup.py`, they want to see what it would delete. Add
a `--dry-run` flag that prints the path of each file it would delete and
deletes nothing.
