---
name: new-batch-explore
description: Pick the next 2–5 roadmap milestones that can be worked in parallel and open a Conductor workspace for each (local or cloud, matching where it runs), started in /opsx:explore mode and named m{milestoneID}-short-name (e.g. m10-alerts). Reads the roadmap from origin (fresh fetch), skips milestones that are done, blocked on someone else, or already in an open workspace. Use when the user runs /new-batch-explore or asks to "start the next batch", "spin up workspaces for the next milestones", or "what should we explore next in parallel".
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

Never propose a milestone that another open workspace is already working on. Names aren't enough (Conductor's own names often drop the milestone number), so for every open workspace of this repo, read its status, last activity, and the first message it was given, which names its milestone:

```bash
DB="${CONDUCTOR_DB_PATH:-$HOME/Library/Application Support/com.conductor.app/conductor.db}"
ROOT="${CONDUCTOR_ROOT_PATH:-$(git rev-parse --show-toplevel)}"
sqlite3 -separator ' | ' "file:$DB?mode=ro" "select w.workspace_name, w.branch, w.workspace_path,
    ifnull(s.status, ''), ifnull(w.last_activity_at, ''),
    replace(substr((select m.content from session_messages m where m.session_id = w.active_session_id
      and m.role = 'user' order by m.created_at limit 1), 1, 200), char(10), ' ')
  from workspaces w left join sessions s on s.id = w.active_session_id
  where w.repository_id = (select id from repos where root_path = '$ROOT') and w.state != 'archived'
  order by w.last_activity_at desc"
```

Then list the OpenSpec changes in each of those workspaces' folders, committed or not: `ls <workspace_path>/openspec/changes` (skip `archive/`). Count a change only if it isn't archived on `origin/$BASE`; an older branch can still show a change that has since been archived. Also note unarchived `openspec/changes/*` on `origin/$BASE` itself.

A milestone is **in flight** if any of these mentions it: a workspace's name, branch or first message, or a change in progress (in a workspace or on `origin/$BASE`). Working or idle doesn't matter: an idle workspace waiting on a decision is still in progress. When unsure whether a workspace covers a milestone, read the end of its transcript (the newest `.jsonl` in `~/.claude/projects/<workspace_path with every character that isn't a letter or digit replaced by ->/`).

## 3. Choose 2–5 milestones

Candidates: not ✅/done, and all of their steps not done. Drop any that are:

- **blocked on someone else**: a "waiting on" table or a step that says "waiting on X" / "once X decides"
- **already in flight**: an open workspace or unarchived change covers it
- **dependent** on an unfinished milestone (e.g. "handover" before the features exist)
- **overlapping** another pick: same screens, tables, or spec files — parallel work would collide

Prefer roadmap order; include a partially-done 🟡 milestone only if its remaining steps are unblocked. Two is fine when the roadmap is thin; never pad to five.

Show the picks as a short table (ID, name, why now, what it avoids) and anything deliberately skipped with its one-line reason. **Ask the user to confirm before creating anything.** Offer lettered alternatives if there's a genuine judgment call.

## 4. Create the workspaces

Workspace name: `m{id}-{short-name}`, so the milestone number shows in Conductor's sidebar. The ID is the roadmap's, lowercased and prefixed with `m` (`10` gives `m10`, `6b` gives `m6b`; an ID that already starts with a letter, like `M9`, stays `m9`). The short name is one or two kebab-case words for the milestone, e.g. `m10-alerts`, `m9-dashboards`. Don't add `explore`: the workspace soon moves past exploring.

Prompt for each milestone:

```
/opsx:explore Milestone {id}: {Milestone title}

From the roadmap ({roadmap path} on origin/{base}):
{the milestone's step table, verbatim}

Explore how to build this milestone. Check the main specs and existing code first, surface open questions and tradeoffs, and recommend a scope for a change proposal. Don't implement anything yet.

Then ask the open decisions one at a time, starting with the one the others depend on. Just before the first one, say: "Once all the decisions are captured, the next step is /opsx:propose." End this message on that first decision.

After the last decision is answered, summarize every decision in one table and end with: "Next step: run /opsx:propose to draft this into a proposal." Don't create the change or write its artifacts from explore mode, and don't ask whether to; /opsx:propose does that.
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

Conductor's namer ignores names in the prompt and picks its own (e.g. "Milestone 10 Alerts Explore"). Once the new row appears, set the name the way a manual rename in the sidebar does. This writes to Conductor's own database, which is undocumented, so back it up once before the first workspace (`sqlite3 "$DB" ".backup '$HOME/conductor-backups/conductor-<timestamp>.db'"`, after `mkdir -p ~/conductor-backups`):

```bash
NAME="m{id}-{short-name}"
WS=$(sqlite3 "$DB" "select local_id from workspaces where repository_id=(select id from repos where root_path='$ROOT') order by created_at desc limit 1")
sqlite3 "$DB" "update workspaces set workspace_name='$NAME', user_set_workspace_name=1 where local_id='$WS'"
```

About a minute later, check `workspace_name` again and set it once more if the namer overwrote it. The branch keeps the namer's name; that's fine.

Tell the user before the first link: "Conductor will pop a Create dialog for each one — press **Enter** to create it, and I'll queue the next." If the poll times out, ask whether they pressed Enter rather than firing the next link.

Do not name a shell variable `path` — zsh ties it to `PATH`.

## 5. Report

List each workspace created (ID, name, what it was told to explore). If a name didn't stick, say so and give the name to set by hand in the sidebar.
