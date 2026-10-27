---
name: new-batch-explore
description: Pick the next 2–5 roadmap milestones that can be worked in parallel and open a Conductor workspace for each (local or cloud, matching where it runs), started in /opsx:explore mode and named {milestoneID}-name-of-milestone. Reads the roadmap from origin (fresh fetch), skips milestones that are done, blocked on someone else, or already in an open workspace. Use when the user runs /new-batch-explore or asks to "start the next batch", "spin up workspaces for the next milestones", or "what should we explore next in parallel".
---

# new-batch-explore

Runs inside a Conductor workspace. Locally, it creates sibling **local** workspaces through Conductor's `conductor://new` deep link, which opens the Create dialog pre-filled; the user presses Enter once per workspace.

**Cloud:** if `CONDUCTOR_IS_LOCAL` is `0`, it creates **cloud** workspaces directly with the `conductor` CLI. Read `cloud.md` (next to this file) and use it for steps 2, 4 and 5. Steps 1 and 3 are the same.

## 1. Read the latest roadmap

Always from the remote, never the working copy:

```bash
git fetch origin -q
BASE="${CONDUCTOR_DEFAULT_BRANCH:-$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|origin/||')}"
BASE="${BASE:-main}"
git ls-tree -r --name-only "origin/$BASE" | grep -iE '(^|/)roadmap\.md$'
git show "origin/$BASE:<that path>"
```

If no `roadmap.md` exists, look for an equivalent (`ROADMAP*`, `docs/plan.md`, `openspec/ROADMAP.md`, a milestones table in README). If nothing fits, stop and ask the user where the roadmap is.

## 2. Find what's already in flight

Conductor's local database lists this repo's open workspaces:

```bash
DB="${CONDUCTOR_DB_PATH:-$HOME/Library/Application Support/com.conductor.app/conductor.db}"
ROOT="${CONDUCTOR_ROOT_PATH:-$(git rev-parse --show-toplevel)}"
sqlite3 "$DB" "select workspace_name, branch from workspaces
  where repository_id=(select id from repos where root_path='$ROOT') and state!='archived'"
```

Also note unarchived `openspec/changes/*` on `origin/$BASE` if the repo uses OpenSpec: a milestone with a change already proposed is in flight.

## 3. Choose 2–5 milestones

Candidates: not ✅/done, and all of their steps not done. Drop any that are:

- **blocked on someone else**: a "waiting on" table or a step that says "waiting on X" / "once X decides"
- **already in flight**: an open workspace or unarchived change covers it
- **dependent** on an unfinished milestone (e.g. "handover" before the features exist)
- **overlapping** another pick: same screens, tables, or spec files — parallel work would collide

Prefer roadmap order; include a partially-done 🟡 milestone only if its remaining steps are unblocked. Two is fine when the roadmap is thin; never pad to five.

Show the picks as a short table (ID, name, why now, what it avoids) and anything deliberately skipped with its one-line reason. **Ask the user to confirm before creating anything.** Offer lettered alternatives if there's a genuine judgment call.

## 4. Create the workspaces

Workspace name: `{id}-{kebab-case milestone name}`. Use the milestone ID **exactly as the roadmap writes it** (lowercased), so it matches how the user refers to it: a roadmap numbered `9` gives `9-client-dashboards`; one using `M9` gives `m9-client-dashboards`; one using `2.3` gives `2.3-client-dashboards`. Conductor derives the sidebar name from the branch its namer picks after the first message, so the prompt leads with the name.

Prompt for each milestone:

```
Workspace/branch name: {id}-{kebab-name}

/opsx:explore Milestone {id}: {Milestone title}

From the roadmap ({roadmap path} on origin/{base}):
{the milestone's step table, verbatim}

Explore how to build this milestone. Check the main specs and existing code first, surface open questions and tradeoffs, and end with a recommended scope for a change proposal. Don't implement anything yet.
```

Fire them **one at a time** — the Create dialog has a single shared draft, so a second link before Enter would overwrite the first:

```bash
ENC=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read()))' <<< "$PROMPT")
ENC_ROOT=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$ROOT")
BEFORE=$(sqlite3 "$DB" "select count(*) from workspaces where repository_id=(select id from repos where root_path='$ROOT')")
open "conductor://new?path=$ENC_ROOT&prompt=$ENC"
# then poll until a new row appears (give the user up to ~3 minutes)
for i in $(seq 1 90); do
  sleep 2
  NOW=$(sqlite3 "$DB" "select count(*) from workspaces where repository_id=(select id from repos where root_path='$ROOT')")
  [ "$NOW" -gt "$BEFORE" ] && break
done
```

Tell the user before the first link: "Conductor will pop a Create dialog for each one — press **Enter** to create it, and I'll queue the next." If the poll times out, ask whether they pressed Enter rather than firing the next link.

Do not name a shell variable `path` — zsh ties it to `PATH`.

## 5. Report

List each workspace created (ID, intended name, what it was told to explore). After the namer runs, Conductor's sidebar should show `{id}-{kebab-name}`; if it shows something else, tell the user they can rename it in the sidebar, or set the repo's "Rename branch" prompt in Conductor's repo settings to always honor a leading `Workspace/branch name:` line.
