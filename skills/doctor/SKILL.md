---
name: doctor
description: Check that powerups is current and that babysitter can work here. Compares the installed plugin and this session's copy with the latest release, checks gh, openspec, the repo's ## babysitter defaults, and (locally) Conductor's database and the outbox table babysitter writes to, or (in the cloud) the conductor CLI's token and which workspaces predate the latest release. Read-only. Use when the user runs /doctor, asks "am I on the latest version?", "why isn't /powerups:x showing?", or before a babysitter run.
---

# doctor

Run it and show its table:

```bash
python3 <this skill's dir>/doctor.py
```

It prints one row per check: ✓ fine, ⚠ worth knowing, ⛔ needs a fix, with the fix in the last column. Below the table, in plain words:

- If any row is ⛔, say what to do first. "This session runs an older copy" means: start a new session in this workspace, nothing else. A version mismatch means: run the update line, then a new session.
- In the cloud, workspaces "created before the latest release" are only a guess from dates: say so, and that only workspaces where the user types `/powerups:` commands need the install; queue and change workspaces are driven by messages and don't.
- An outbox-table ⛔ means a Conductor update changed its database. Babysitter still works, falling back to Claude's `SendMessage` (messages won't show in the workspace chats). Suggest opening an issue on the plugin with the doctor output.

Don't fix anything yourself; the fixes touch the user's Claude config and Conductor settings.
