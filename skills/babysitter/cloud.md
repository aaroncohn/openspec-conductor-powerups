# babysitter in a Conductor cloud workspace

Read this when `CONDUCTOR_IS_LOCAL` is `0`. Every workspace runs in its own Linux sandbox, so there are no sibling worktrees, no `ListAgents`, and no `SendMessage`. Use the `conductor` CLI instead; it's on the `PATH` in cloud workspaces. These sections replace steps 1, 3 and 4 of `SKILL.md`. Everything else applies as written.

If `conductor` fails with an auth error, tell the user that the workspace has no API token: they can turn on automatic API access in Conductor → Settings → General (it applies to new workspaces) or set their own `CONDUCTOR_API_KEY`. Stop until it works.

## 1. Find the workspaces

```bash
git fetch origin -q
REPO=$(basename -s .git "$(git remote get-url origin)")
conductor workspace list --mine --repo "$REPO" --json --limit 100     # page with --offset while hasMore
conductor workspace session <workspaceId> --json                      # its sessions
```

Skip this workspace (`$CONDUCTOR_WORKSPACE_ID` if set, otherwise match by name). You can't read other sandboxes' files, so decide scope from each workspace's branch and transcript:

- **In scope:** it ran `/opsx:propose` (or its pushed branch has a change under `openspec/changes/` that isn't archived on `origin/main`) and the change isn't merged yet.
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

## 3. Messaging a session

Write each message to a file first (it avoids shell quoting problems), then send it:

```bash
conductor message create --session <sessionId> --message-file .context/msg-<n>.md
```

The header line and rules from step 3 still apply. Two cloud additions for the rules:

- Sessions can't message you back. Tell them to put anything you need (PR URL, questions, setup only the user can do) in their final reply, where you'll read it.
- Anything that needs the user's own machine (their browser and its logins, local files) can't be done from the cloud. Treat it as user setup (step 5) and write the handoff block for a **local** workspace.

## 4. Watching them

There are no idle notifications in the cloud. Run a watcher in the background (Bash `run_in_background`) so you're woken when a session stops working, and re-start it after each event. Fire only on a **change** to idle: a session can sit idle while its own background job (tests, CI watch) runs, and a watcher that fires on any idle state wakes you over and over for nothing.

```bash
cat > .context/watch.sh <<'EOF'
#!/usr/bin/env bash
# Exits with "<sessionId> <status>" when a watched session goes from working to anything else.
declare -A last
while true; do
  for s in "$@"; do
    st=$(conductor --json session status "$s" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status") or "")' 2>/dev/null)
    [ -z "$st" ] && continue
    if [ "${last[$s]}" = working ] || [ "${last[$s]}" = queued ]; then
      [ "$st" != working ] && [ "$st" != queued ] && { echo "$s $st"; exit 0; }
    fi
    last[$s]=$st
  done
  sleep 60
done
EOF
chmod +x .context/watch.sh
.context/watch.sh <sessionId> <sessionId> ...      # run in the background
```

A session that is already idle when you start won't trigger it, so check those right away by reading their transcripts. When it fires, read that session's new messages, check its PR, act, and re-start the watcher for the sessions still in flight.

If a session stops responding or its workspace is gone, do the step yourself from this sandbox (`git fetch origin <branch>` and work on that branch) and say so in the update.
