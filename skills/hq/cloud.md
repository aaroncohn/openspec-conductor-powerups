# babysitter in a Conductor cloud workspace

Read this when `CONDUCTOR_IS_LOCAL` is `0`. Every workspace runs in its own Linux sandbox, so there are no sibling worktrees, no `ListAgents`, and no `SendMessage`. Use the `conductor` CLI instead; it's on the `PATH` in cloud workspaces. These sections replace the one-HQ check, steps 1 and 3, and step 4's watcher in `SKILL.md`; step 4's other rules, its re-scan and merge lock included, still apply. Everything else applies as written, including what `main` means.

If `conductor` fails with an auth error, tell the user that the workspace has no API token: they can turn on automatic API access in Conductor → Settings → General (it applies to new workspaces) or set their own `CONDUCTOR_API_KEY`. Stop until it works.

## One HQ per repo

Before anything else:

```bash
git fetch origin -q
REPO=$(basename -s .git "$(git remote get-url origin)")
conductor workspace list --mine --repo "$REPO" --name "Babysitter HQ" --json | python3 <this skill's dir>/state.py other-hq
```

A non-zero exit means stop, as in `SKILL.md`. It skips `$CONDUCTOR_WORKSPACE_ID`; if that isn't set and the one it names is this workspace, carry on. `--mine` is on purpose: someone else's HQ only drives their own workspaces.

## 1. Find the workspaces

```bash
conductor workspace list --mine --repo "$REPO" --json --limit 100     # page with --offset while hasMore
conductor workspace session <workspaceId> --json                      # its sessions
```

Skip this workspace (`$CONDUCTOR_WORKSPACE_ID` if set, otherwise match by name), and name it `Babysitter HQ` so the user can find it in the sidebar: `conductor workspace rename <its id> --name "Babysitter HQ"`. You can't read other sandboxes' files, so decide scope from each workspace's branch and transcript:

- **In scope:** it ran `/opsx:propose` (or its pushed branch has a change under `openspec/changes/` that isn't archived on `origin/main`) and the change isn't merged yet. Also in scope: it has an open PR, or its session last stopped asking whether to commit, open a PR or merge.
- **Skipped:** still exploring, already merged and archived, or unrelated. List them as skipped.

Read the transcripts with the scan. This is the re-scan from step 4 of `SKILL.md`: run it on every wake, for any reason, before you act, post or restart the watcher.

```bash
python3 <this skill's dir>/watch.py scan "$REPO"
```

For each open workspace it prints every new user message and the last few assistant ones. It fetches only what's new (`conductor session message --after <lastMessageId>`, or the end of the transcript the first time), and gives a workspace whose `lastActivityAt` hasn't changed since the last scan one line. It keeps its place in `.context/babysitter-scan.json`. It marks each workspace whose user typed `/opsx:propose` (or `/opsx:ff`, `/opsx:continue`, `/opsx:apply`) in the state file, and ends with the `ADOPT NOW` line for those you aren't driving yet: take each over before you post anything (step 4 of `SKILL.md`). Then comes the `CHECK NOW` line: workspaces whose session offered to start `/opsx:propose` and the user answered, or that named `/opsx:apply`. Read and decide each, as in step 4. Judge the rest from the messages it prints: a workspace whose user asked for the proposal in plain words counts too. If it says it can't read a workspace, nothing about that workspace is verified: say so in the digest and don't update its row. The CLI doesn't give a workspace's branch, so find its PR from the branch its transcript names (`gh pr list --head <branch> --state all`), or with `gh pr list --search <name>`.

## 2. The state file

`state.py` works here as written. For the scan, pipe the CLI's list into it: `conductor workspace list --mine --repo "$REPO" --json --limit 100 | python3 <this skill's dir>/state.py sync-scan` (it skips `$CONDUCTOR_WORKSPACE_ID`). The CLI doesn't know stages or PRs, so `sync-scan` keeps the old stage, which may be stale. After each re-scan (section 1), set them yourself for anything that changed: `state.py workspace set <name> --stage apply --pr 12`.

## Stage in the workspace name

Rename with `conductor workspace rename <workspaceId> --name <new name>`, starting from the name `workspace list` shows. You can't run `openspec status` in another sandbox, so judge `propose` versus `apply` from its pushed branch (the change has a `tasks.md`) or its transcript (it finished `/opsx:propose`). A workspace with an open PR but no OpenSpec change is `apply`. Judge by its newest PR: an older merged PR doesn't make it `archive` if it has newer work.

## 3. Messaging a session

Write each message to a file first (it avoids shell quoting problems), then send it:

```bash
conductor message create --session <sessionId> --message-file .context/msg-<n>.md
```

The `Via Babysitter: ` prefix and rules from step 3 still apply. Send a workspace's first brief once its session has finished its current turn (`conductor session status <sessionId> --json` isn't `working`), not in the middle of it. These messages show in the workspace's chat. Two cloud additions for the rules:

- Sessions can't message you back. Tell them to put anything you need (PR URL, questions, setup only the user can do) in their final reply, where you'll read it.
- Anything that needs the user's own machine (their browser and its logins, local files) can't be done from the cloud. Treat it as a user action (step 5), and write any browser prompt for the user's **local** browser, with the `browser-handoff` skill if it's installed.

## 4. Watching them

There are no idle notifications in the cloud. Run the watcher in the background (Bash `run_in_background`) and re-start it after each event. It stays quiet until there's something to act on, then exits and prints what: a session finished a turn, a session has been working for 30 minutes with no update, or (it checks every 10 minutes) a workspace of this repo is new, gone, or has new activity while none of its sessions is being watched. It skips this workspace by itself. `--ignore` is for the workspaces marked `--monitoring no`.

```bash
python3 <this skill's dir>/watch.py watch "$REPO" --ignore "$(python3 <this skill's dir>/state.py ignored)" <sessionId> <sessionId> ...      # run in the background
```

Start it just before you send a message (so the turn it triggers counts). Give it a background timeout of 30 minutes at most, and sooner if the next digest (step 6) or the merge lock's 45 minutes come first. Whether it exits or times out, you woke: re-scan (section 1), then act as in step 4 of `SKILL.md`, and re-start the watcher for the sessions still in flight. Stay silent if nothing changed.

If a session stops responding or its workspace is gone, do the step yourself from this sandbox (`git fetch origin <branch>` and work on that branch) and say so in the next digest.

## 9. Creating Open Actions, Open Decisions and Open Tests

Find them by name in `conductor workspace list --mine --repo "$REPO" --json`. To create one, write the queue prompt to a file, then:

```bash
conductor workspace create --repo-url "$(git remote get-url origin)" --name "Open Decisions" --branch <default branch> --agent claude --message-file .context/open-decisions.md --json
```

(`--name "Open Actions"` or `--name "Open Tests"` for the others.) Always pass `--repo-url`: without it the CLI guesses the project, and a queue on the wrong repo is useless. Check it's in `workspace list --mine --repo "$REPO"` before sending anything. Then send items with `conductor message create`, as in section 3. The queue session can't message you back: read its "Done:", "Answered:" and "Result:" lines from its transcript, and watch it with the watcher in section 4.
