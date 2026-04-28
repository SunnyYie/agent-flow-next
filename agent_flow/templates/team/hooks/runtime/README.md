# Team Runtime Hooks Layout

`runtime/` hooks are split by responsibility:

- `guards/`: hard/soft policy guards before dangerous operations.
- `enforcers/`: workflow enforcers and phase gates.
- `trackers/`: state/evidence trackers after tool execution.
- `reminders/`: non-blocking reminders and nudges.

Root-level runtime hooks were removed. Register hook commands directly to
the files under these subdirectories.
