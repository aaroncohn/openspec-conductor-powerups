# babysitter in a Conductor cloud workspace

Read this when `CONDUCTOR_IS_LOCAL` is `0`. Every workspace runs in its own Linux sandbox, so there are no sibling worktrees, no `ListAgents`, and no `SendMessage`. Use the `conductor` CLI instead; it's on the `PATH` in cloud workspaces. These sections replace steps 1, 3 and 4 of `SKILL.md`. Everything else applies as written, including what `main` means.

If `conductor` fails with an auth error, tell the user that the workspace has no API token: they can turn on automatic API access in Conductor → Settings → General (it applies to new workspaces) or set their own `CONDUCTOR_API_KEY`. Stop until it works.

## 1. Find the workspaces

```bash
git fetch origin -q
REPO=$(basename -s .git "$(git remote get-url origin)")
conductor workspace list --mine --repo "$REPO" --json --limit 100     # page with --offset while hasMore
conductor workspace session <workspaceId> --json                      # its sessions
```

Skip this workspace (`$CONDUCTOR_WORKSPACE_ID` if set, otherwise match by name), and name it `Babysitter HQ` so the user can find it in the sidebar: `conductor workspace rename <its id> --name "Babysitter HQ"`. You can't read other sandboxes' files, so decide scope from each workspace's branch and transcript:

- **In scope:** it ran `/opsx:propose` (or its pushed branch has a change under `openspec/changes/` that isn't archived on `origin/main`) and the change isn't merged yet. Also in scope: it has an open PR, or its session last stopped asking whether to commit, open a PR or merge.
- **Skipped:** still exploring, already merged and archived, or unrelated. List them as skipped.

Read a session's transcript with `conductor session message`. Messages come oldest first, so page with `--offset` until `hasMore` is false, keep the last message id, and from then on fetch only new ones with `--after <lastMessageId>`. To see what the session last said:

```bash
conductor session message <sessionId> --json --limit 100 --offset <n> | python3 -c '
import json, sys
for m in json.load(sys.stdin)["data"]:
    p = (m.get("content") or {}).get("rawPayload") or {}
    if m["type"] == "agent" and p.get("type") == "assistant":
        for c in p["message"].get("content", []):
            if c.get("type") == "text": print(c["text"])' | tail -20
```

## Stage in the workspace name

Rename with `conductor workspace rename <workspaceId> --name <new name>`, starting from the name `workspace list` shows. You can't run `openspec status` in another sandbox, so judge `propose` versus `apply` from its pushed branch (the change has a `tasks.md`) or its transcript (it finished `/opsx:propose`). A workspace with an open PR but no OpenSpec change is `apply`. Judge by its newest PR: an older merged PR doesn't make it `archive` if it has newer work.

## 3. Messaging a session

Write each message to a file first (it avoids shell quoting problems), then send it:

```bash
conductor message create --session <sessionId> --message-file .context/msg-<n>.md
```

The `Via Babysitter: ` prefix and rules from step 3 still apply. These messages show in the workspace's chat. Two cloud additions for the rules:

- Sessions can't message you back. Tell them to put anything you need (PR URL, questions, setup only the user can do) in their final reply, where you'll read it.
- Anything that needs the user's own machine (their browser and its logins, local files) can't be done from the cloud. Treat it as a user action (step 5), and write any browser prompt for the user's **local** browser, with the `browser-handoff` skill if it's installed.

## 4. Watching them

There are no idle notifications in the cloud. Run a watcher in the background (Bash `run_in_background`) and re-start it after each event. It stays quiet until there's something to act on, then exits and prints what: a session finished a turn, a session has been working for 30 minutes with no update, or a new workspace of this repo appeared (it checks every 10 minutes). It notes each session's `updatedAt` when it starts, so a short turn that starts and ends between checks still counts, and a session already sitting idle doesn't fire.

```bash
cat > .context/watch.py <<'EOF'
# Usage: watch.py <repo> [<sessionId> ...]. Prints why and exits when there's something to act on.
import json, subprocess, sys, time
repo, sessions = sys.argv[1], sys.argv[2:]
def cli(*args):
    r = subprocess.run(["conductor", "--json", *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}
def status(s):
    d = cli("session", "status", s)
    return d.get("status") or "", d.get("updatedAt") or ""
def workspaces():
    return {w["id"]: w["name"] for w in cli("workspace", "list", "--mine", "--repo", repo, "--limit", "100").get("data", [])}
start = {s: status(s)[1] for s in sessions}
seen = {s: (start[s], time.time()) for s in sessions}
known, last_scan = workspaces(), time.time()
while True:
    time.sleep(30)
    for s in sessions:
        st, updated = status(s)
        if st and st not in ("working", "queued") and updated != start[s]:
            sys.exit(print(s, "finished a turn"))
        if st != "working" or updated != seen[s][0]:
            seen[s] = (updated, time.time())
        elif time.time() - seen[s][1] > 30 * 60:
            sys.exit(print(s, "has been working for 30 minutes with no update"))
    if time.time() - last_scan > 10 * 60:
        now, last_scan = workspaces(), time.time()
        new = [now[w] for w in now if known and w not in known]
        if new:
            sys.exit(print("new workspace:", ", ".join(new)))
        known = now or known
EOF
python3 .context/watch.py "$REPO" <sessionId> <sessionId> ...      # run in the background
```

Start it just before you send a message (so the turn it triggers counts), and check sessions that were already idle when you started by reading their transcripts. When it fires, read that session's new messages, check its PR, act, and re-start the watcher for the sessions still in flight.

The watcher can't see a stage change in a workspace you aren't watching (for example, the user just ran `/opsx:propose` there), so give it a background timeout of 30 minutes, or less if the next digest (step 6) is due sooner. When it times out, redo section 1's scan, then rename and adopt as in step 4 of `SKILL.md`. Stay silent if nothing changed.

If a session stops responding or its workspace is gone, do the step yourself from this sandbox (`git fetch origin <branch>` and work on that branch) and say so in the next digest.

## 9. Creating Open Actions, Open Decisions and Open Tests

Find them by name in `conductor workspace list --mine --repo "$REPO" --json`. To create one, write the queue prompt to a file, then:

```bash
conductor workspace create --name "Open Decisions" --branch <default branch> --agent claude --message-file .context/open-decisions.md --json
```

(`--name "Open Actions"` or `--name "Open Tests"` for the others.) Then send items with `conductor message create`, as in section 3. The queue session can't message you back: read its "Done:", "Answered:" and "Result:" lines from its transcript, and watch it with the watcher in section 4.
