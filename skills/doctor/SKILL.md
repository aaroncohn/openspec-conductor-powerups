---
name: doctor
description: Check that the plugin is current and that babysitter can work here. Compares the installed plugin and this session's copy with the latest release, checks gh, openspec, the repo's ## babysitter defaults, and (locally) Conductor's database and the outbox table babysitter writes to, or (in the cloud) the conductor CLI's token and which workspaces predate the latest release. Read-only. Use when the user runs `/babysitter:doctor`, asks "am I on the latest version?", "why isn't `/babysitter:x` showing?", or before a babysitter run.
---

# doctor

Run it and show its table:

```bash
python3 <this skill's dir>/doctor.py
```

Add `--send-test` when the user asks whether babysitter's messages will show in the workspace chats, or after a Conductor update: it sends one message to this session through babysitter's local path and reports whether it landed (it shows up in this chat as "Via Babysitter: doctor test"; that's expected). It prints one row per check: ✓ fine, ⚠ worth knowing, ⛔ needs a fix, with the fix in the last column. Below the table, in plain words:

- If any row is ⛔, say what to do first. "This session runs an older copy" means: start a new session in this workspace, nothing else. A version mismatch means: run the update line, then a new session.
- In the cloud, workspaces "created before the latest release" are only a guess from dates: say so, and that only workspaces where the user types `/babysitter:` commands need the install; queue and change workspaces are driven by messages and don't.
- An "organization switcher" ⛔ means Conductor is on a cloud organization: the Create dialog that new-batch-explore and babysitter open would make cloud workspaces on another repo. The fix is the switcher at the top left of Conductor.
- An "installed after this workspace was created" ⛔ (cloud) means the plugin was installed after the workspace's first session started, by a `SessionStart` hook or by a Setup script that failed or was still running. The user should make sure the repository's Setup script has the install line (Conductor's cloud organization settings, not `.conductor/settings.toml`). If it already does, they should check that script's output in a fresh workspace for errors or slowness. Meanwhile: type the full `/babysitter:…` name, which works even when the picker doesn't list it. The picker catches up after a few sessions.
- An outbox-table or send-test ⛔ means a Conductor update changed its database or messaging. Babysitter still works, falling back to Claude's `SendMessage` (messages won't show in the workspace chats). Suggest opening an issue on the plugin with the doctor output.

Don't fix anything yourself; the fixes touch the user's Claude config and Conductor settings.
