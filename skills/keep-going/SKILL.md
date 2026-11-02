---
name: keep-going
description: Pick up babysitter where `/babysitter:pause` left off, catching up on what happened and telling the held sessions to carry on. Run it in the Babysitter HQ workspace; anywhere else it changes nothing and says so.
disable-model-invocation: true
---

# keep-going

1. Run `python3 <this skill's dir>/../hq/state.py resume` from this workspace's root. If it errors, this isn't Babysitter HQ: pass on what it said, change nothing, and stop. If it says not paused, say so and stop. Otherwise it lists the sessions to release, one per line: name, then session.
2. Read `<this skill's dir>/../hq/SKILL.md` (and `cloud.md` beside it if `CONDUCTOR_IS_LOCAL` is `0`), then `state.py show` and `.context/babysitter-notes.md`. This may be a new or compacted session, and those rules apply again from here.
3. Catch up on the pause: update this workspace to the latest `main`, do a fresh scan into `state.py sync-scan`, read each held session's last messages and its PR, and read the queues for answers that came back. Handle those answers (hq step 9), rename what changed stage, and adopt what's new (step 4).
4. Start the watcher (step 4), then send each released session, plus any other you held:

   > Via Babysitter: resumed. Carry on from where you stopped, with the same rules as before; merging to `main` is approved.

   Add the answer if it's waiting on one. A session the user took further by hand during the pause carries on from there. Skip `--now`.
5. Set the goal again (hq step 0).
6. Post a full digest (step 6), opening with "Resumed; paused for about <how long>." and saying which estimates moved because of the pause. Then `state.py digest-posted`.
