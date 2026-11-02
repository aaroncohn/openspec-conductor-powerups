---
name: pause
description: Pause babysitter for now, so nothing new ships until `/babysitter:keep-going`. Run it in the Babysitter HQ workspace; anywhere else it changes nothing and says so.
disable-model-invocation: true
---

# pause

The user wants babysitter to stop for now, with nothing new shipping until `/babysitter:keep-going`.

1. Run `python3 <this skill's dir>/../hq/state.py pause` from this workspace's root. If it errors, this isn't Babysitter HQ: pass on what it said, change nothing, and stop. If it says already paused, say so and stop. Otherwise it lists the sessions to hold, one per line: name, then session.
2. Stop babysitter's own background work with `TaskStop`: its watcher, a `send` still waiting, a `gh ... --watch`. Don't `pkill`: another repo's HQ runs the same script. Don't cancel a CI run or deploy already running; note it for step 4.
3. Hold each listed session, plus any other you've been driving, with this message:

   > Via Babysitter: the user has paused babysitting. Finish the step you're on, then stop. Until a "Via Babysitter: resumed" message, don't merge, archive or start the next step, unless the user tells you to here. Reply in one line with where you stopped.

   Locally: `python3 <this skill's dir>/../hq/conductor-local.py send <session> <file> --now`, because a working session may be about to merge. In the cloud: `conductor message create`, as in hq's `cloud.md` section 3; the listed ID is the workspace, so get its session with `conductor workspace session <id> --json`. Don't touch the Open Actions, Open Decisions or Open Tests workspaces.
4. Post this, in plain words, with the first line exactly as written:

```
Babysitter is paused.
Held: <the workspaces>. <Any you couldn't reach, and what they may still do.>
Still finishing: <any merge, CI run or deploy already underway; leave this line out if there are none>
Open Actions, Decisions and Tests still work; I'll handle your answers when you keep going.
Run `/babysitter:keep-going` to pick up where this left off. If `◎ /goal active` still shows, run `/goal clear`.
```

Then follow hq's "Paused" rule: end every later turn with no text, unless the user asks you something.
