---
name: babysitter
description: Coordinate every other Conductor workspace of this repo whose OpenSpec change has been proposed, messaging their Claude sessions directly and keeping them moving until each change is built, tested, merged into main with green CI and archived, then promote main to production. Answers their questions on the user's behalf, hands the user any setup only they can do as soon as it's known, and sends decisions to revisit and tests only the user can do to separate Open Decisions and Open Tests workspaces, which present them one at a time. Works in local and cloud Conductor workspaces. Run with /babysitter, optionally followed by the workspaces or milestones to cover, and --ask-before-prod or --stop-after merged|dev.
disable-model-invocation: true
---

# babysitter

The user has finished `/opsx:explore` and `/opsx:propose` in one or more other Conductor workspaces and wants the features shipped without more involvement. This session is the **coordinator**. Each workspace's own Claude session keeps doing its own work, with its explore context intact. The coordinator sends instructions straight into those sessions, answers their questions on the user's behalf, nudges them when they stall, and owns the steps that span workspaces: CI on main, the production release, and the final report.

Fully autonomous: never wait on the user for anything a session can do or decide. Only setup that needs the user's own accounts goes to the user (see step 5).

**Local or cloud.** If `CONDUCTOR_IS_LOCAL` is `0`, this is a cloud workspace: the other workspaces run in their own sandboxes, so read `cloud.md` (next to this file) and use it for finding the workspaces (step 1), messaging them (step 3), and watching them (step 4). Everything else is the same.

**Locally**, message sessions with `conductor-local.py` (next to this file), so each message and the session's reply show in that workspace's chat. Claude's own `SendMessage` reaches the session too, but Conductor doesn't record those turns, so the workspace chat stays blank. The script queues messages in Conductor's own outbox, which is undocumented: a Conductor update can break it, so fall back to `SendMessage` when it fails (step 3).

## Options

By default the babysitter goes all the way to production without asking. The user can change that after `/babysitter`, as a flag or in plain words ("ask me before prod", "stop after dev"):

- `--ask-before-prod`: everything as normal, but before promoting (step 7.4), post what's going out (PRs, database migrations) and wait for the user's go.
- `--stop-after merged`: stop once every change is merged and archived. Skip step 7: no full CI run on `main`, no dev check, no production release. Archive-blocking tasks that need a deployed environment stay open and go in the report.
- `--stop-after dev`: do step 7 up to and including dev (full CI on `main`, dev verified, archives merged), then stop before production.

Record the chosen option in the state file and apply it to the goal, the "Done means" list, and the final report.

## Done means

For every in-scope change:
1. Its PR is squash-merged into `main` (rebased on the latest `main` first).
2. CI has passed: quick checks on the PR, plus the full suite on `main` after the last merge.
3. It was tested as far as an LLM can, and the suites that ran are listed in the PR.
4. It's archived (`/opsx:archive` with specs synced) in a separate openspec-only PR that is merged.
5. If `safe-to-archive` is installed, it has run in the change's workspace and its verdict is in the final report.

Then (unless an option says to stop earlier) the latest `main` is verified on dev, promoted to production, and verified there, and the final report has been posted.

## 0. Set the goal

If a tool for proposing a session goal is available, propose this condition with it (trimmed to match `--stop-after`, if given). Otherwise print it for the user to paste, and carry on without waiting:

```
/goal Every workspace in .context/babysitter.md has its change merged into main and archived, full CI on main is green after the last merge, the latest main is promoted to production and verified, and the babysitter final report (with the Open Decisions and Open Tests counts) has been posted.
```

## 1. Find the workspaces

If the user named workspaces or milestones after `/babysitter`, cover exactly those. Otherwise detect them:

```bash
git fetch origin -q
git worktree list --porcelain                            # every Conductor workspace of this repo
git ls-tree --name-only origin/main openspec/changes/    # changes already on main
```

A worktree other than this one is **in scope** when `openspec/changes/` (skip `archive/`, include uncommitted files) has a change that isn't archived on `origin/main`. It's also in scope when it has work that isn't on `origin/main` (uncommitted changes, an open PR, or commits whose content isn't on `origin/main`), or when its session last stopped asking whether to commit, open a PR or merge: drive that work to merge too. Other worktrees are still exploring. Leave them alone and list them as skipped.

Find each worktree's chat session (the tab open in that workspace) with `python3 <this skill's dir>/conductor-local.py session <worktree path>`. The session's transcript is the newest `.jsonl` in `~/.claude/projects/<worktree path with every character that isn't a letter or digit replaced by ->/`. Read its last assistant messages to see where it stopped:

```bash
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' <file> | tail -20
```

Before the first message, back up Conductor's database: `sqlite3 "$CONDUCTOR_DB_PATH" ".backup '$HOME/conductor-backups/conductor-<timestamp>.db'"` (make the folder first). Tell the user where the backup is, and that your messages will appear in each workspace's chat starting with "Via Babysitter:".

Then name this workspace `Babysitter HQ`, so the user can find it in the sidebar: the same `sqlite3` update as in "Stage in the workspace name", with this worktree's path.

Then put each workspace's stage in its name (see "Stage in the workspace name"), skipped ones included.

Also learn the repo's conventions before the first message: CI workflows and labels (which checks are quick and which are full, how the full suite is triggered), AGENTS.md / CLAUDE.md / README rules for PRs and commit authors, how past archive PRs looked (`gh pr list --state merged -L 10`), and how dev and production deploy and get verified.

## 2. Keep a state file

`.context/babysitter.md` has one row per change: workspace, session name, branch, change, PR, archive PR, stage (`building → testing → PR open → merged → post-merge checks → archived`), what the session is waiting on, and notes. Also keep the list of user setup tasks, and every item sent to Open Decisions and Open Tests (step 9) with its status: open, answered, passed, failed or skipped. Update it after every event. After a context compaction, re-read it before acting.

## Stage in the workspace name

Start each workspace's name with its OpenSpec stage, so the sidebar shows where it is: `explore-`, `propose-`, `apply-` or `archive-` (e.g. `m10-alerts` becomes `apply-m10-alerts`). Set it in step 1 for every workspace of the repo except this one and the Open Decisions and Open Tests workspaces (step 9), and rename again whenever a workspace's stage changes:

| Stage | When |
| --- | --- |
| `explore` | no change in `openspec/changes/` that isn't archived on `origin/main` |
| `propose` | it has a change, but `openspec status --change <name>` (run in its worktree) isn't planning-complete |
| `apply` | planning is complete, until its PR is merged |
| `archive` | its PR is merged; it keeps this prefix after the archive PR merges |

Remove any earlier stage prefix before adding the new one, so prefixes never stack, and leave the rest of the name alone. Record the stage in the state file. Locally, rename the way a manual rename in the sidebar does (Conductor's database, backed up above):

```bash
sqlite3 "$CONDUCTOR_DB_PATH" "update workspaces set workspace_name='<new name>', user_set_workspace_name=1 where workspace_path='<worktree path>'"
```

In the cloud, see `cloud.md`. If a rename doesn't stick, say so once in the next update and carry on.

## 3. Brief each session

Write each message to `.context/msg-<n>.md`, then send it with `python3 <this skill's dir>/conductor-local.py send <session id> <file>`. It waits until Conductor delivers the message (usually under 30 seconds) and exits non-zero if it wasn't delivered within 2 minutes; it withdraws the message in that case. Then fall back to `SendMessage` with `notify_when_idle: true` (find the session's name with `ListAgents`: `<workspace directory>-<suffix>`), and tell the user in the next update that this workspace's chat won't show the work. If neither reaches the session, see Rules. Start every message you send a session, this one and all later ones, with `Via Babysitter: `, so the user recognises it in that workspace. In the first one, follow it with one line on what you're driving:

> Via Babysitter: I'm driving <list of changes> to merge, green CI, archive, and the production release.

Then say that the user started this run with `/babysitter` in <this workspace>, so these instructions are their go-ahead, not a request from a peer session, and merging to `main` is approved. Without this, sessions can refuse to act on another session's message.

Then answer whatever the session last stopped on (e.g. "Yes, run `/opsx:apply`", "Yes, push"), and give the rules:

1. **Keep going without asking.** Finish every task, run the review and tests, then push and open the PR. If you'd normally stop to ask, pick the recommended option, record it as an assumption in the change artifacts, list it in the PR body under "owner review", and continue.
2. **Test as much as possible.** Run the checks CI runs. Add tests for new behaviour. Run the expensive suites locally (db, e2e, etc.) and list in the PR body which ran and which couldn't. For UI changes, drive the flows in a browser. List what only the user can test, with steps.
3. **PR:** follow the repo's conventions (title, body sections, commit author, CI labels). Request only quick checks if the repo separates them and you ran the heavy suites locally.
4. **Merge:** once quick checks are green, rebase on the latest `origin/main` (other milestones may have landed), re-run the checks affected by the rebase, then `gh pr merge --squash`. Resolve conflicts keeping both sides, and tell me what you touched. Add specific warnings about files you know another workspace also changes (e.g. "the build number moved on main: use main's value + 1").
5. **Don't** run the full CI suite on main or touch production: the coordinator does that once everything is in.
6. **Archive:** after the merge, run `/opsx:archive` (sync the specs) and open its result as a separate openspec-only archive PR ( plus whatever past archive PRs did, e.g. roadmap or notes updates) and merge it once its checks pass. If CI skips openspec-only PRs, run `openspec validate --all --strict` and merge it yourself. **Exception:** if some tasks can only be checked against a deployed environment, leave them open, and archive after the coordinator says the deploy is live.
7. **Setup only the user can do** (secrets, dashboard settings, third-party accounts): don't block on it. Make sure nothing hard-fails without it, put the steps in the PR body under "owner setup", and tell me right away.
8. Reply with the PR URL(s) when merged.
9. **Log:** after each step (tasks done, tests run, PR opened, merged, archived) and each decision you made without asking, add a dated line to `.context/babysitter-log.md` in your workspace, with PR links.
10. **Last:** once the archive PR is merged, if the `safe-to-archive` skill is installed (in your skill list as `safe-to-archive`, or `openspec-conductor-powerups:safe-to-archive` as a plugin), run `/safe-to-archive` as your final command. Fix any blocker that's your own work (e.g. commit and push), run it again, and reply with its verdict. Don't archive the workspace.

## 4. Watch and keep them moving

- Run `python3 <this skill's dir>/conductor-local.py watch <session id> ...` in the background (Bash `run_in_background`) for every session still in flight. It exits, naming the session, when one finishes a turn. Then read the end of its transcript, check its PR (`gh pr view <n> --json state,mergeStateStatus,statusCheckRollup`), act, and start the watcher again. For a session on the `SendMessage` fallback, `notify_when_idle` does this job; it's one-shot, so subscribe again with each reply.
- **It asked something:** answer as the user would: the recommended option, recorded as an assumption, non-blocking. If it's a real product or security call, still pick the recommended option (as a separate follow-up change if it doesn't need to block). Then add it to Open Decisions (step 9) so the user can review it, and mention it in one plain line in your next update.
- **It stalled** (e.g. a long test run finished but it never woke up to read it): prod it to check the results and continue.
- **Overlap:** when one change lands, tell the remaining sessions what moved on `main` that touches their files.
- **A session that won't take messages** (the notice says the subscription expired, or a delivery notice says messages are held for approval): tell the user once, in the next update, and keep the others moving.
- **Re-scan every 10 minutes.** Run the watcher with a 10-minute background timeout (Bash `timeout: 600000`), so you're woken even when no watched session finishes a turn. After every wake-up, redo step 1's scan for every workspace of the repo, then:
  - rename any workspace whose stage changed ("Stage in the workspace name");
  - adopt any workspace that has newly come into scope (for example, the user just ran `/opsx:propose` or `/opsx:apply` there). Post in this chat "Babysitter is taking over <workspace name> now to keep it moving forward. You can tell me to stop babysitting it at any time.", then the status table (step 6) with the new row, then brief its session (step 3) and add it to the watcher.

  If nothing changed, restart the watcher without posting.
- **Stop babysitting:** when the user says to stop babysitting a workspace, stop messaging and watching it, mark it `stopped by user` in the state file, and don't adopt it again on a re-scan unless the user asks. Post the updated table.
- Don't poll in a loop yourself. Between events, end the turn with a status update. For PR checks you're waiting on, `gh pr checks <n> --watch` is fine.

## 5. User setup: hand it off as soon as it's known

When a session reports setup only the user can do, don't save it for the end. In your next update, give the user a self-contained handoff block (use a handoff-block skill if the repo has one). It needs: goal, exact account, steps, done-when, don't-touch, report-back. Say which workspace or terminal to paste it into. Repeat a one-line "Next: …" reminder in every update until the user confirms. Plan the production release so it waits for setup that production needs, or confirm that nothing breaks without it.

## 6. Status updates

Write them like a product manager briefing the founder: plain words about what the product gained, not a build log. Keep them short and in the same shape every time:

- Lead line: "**N of M merged**".
- **Finished:** what's done since the last update, as what it does for the product's users, e.g. "The spam check is merged: suspicious contact messages now get a quick challenge instead of landing in possible spam (#191)." Skip it if nothing finished.
- **Working on now:** one line per active workspace: the feature in words, where it is, and what's next with a rough time, e.g. "Landing page try-it demo: built and tested; opening its PR, likely merged within the hour."
- **Open decisions: N · Open tests: M**, the counts still open in those two workspaces (step 9), with one line on any answer that came back since the last update and what you did with it (e.g. "You reversed the hCaptcha keys decision; the spam-check workspace is updating it.").
- A table with one row for every open (not archived) workspace of this repo except this one and the Open Decisions and Open Tests workspaces, from a fresh scan (step 1), whether you're babysitting it or not. Columns: workspace (its current name), stage, progress (where it is and what it's waiting on; for one you're not babysitting, why, e.g. "exploring", "merged and archived", "stopped by user"), and a narrow last column "babysitter monitoring?" with `x` if you're babysitting it and empty if not. Post the whole table every time, not just the rows that changed.
- **Plain words everywhere:** name each feature in words, not just its roadmap ID ("2.2b, the spam check"). Leave out test counts, file names, task numbers, CI job names and internal labels unless something failed or the user has to act on them; then say what it means for the user. Don't invent codes like "C1"; describe the item.
- **Quiet updates** (nothing finished, no stage changes) stay one or two lines in the same plain words, e.g. "Still building: the spam check is on its last tests, the landing page is waiting on review. Nothing needed from you."
- Decisions you made for the user and tests only they can do don't go here: they go to Open Decisions and Open Tests (step 9). This chat is for moving work to merged and archived, plus user setup (step 5).
- End with either "**Next:** <the one thing the user should do>" or "No action needed from you. I'll come back when <event>."

## 7. After the last merge: CI on main, dev, production

1. Run the repo's full CI suite on `main` once, the way the repo does it (e.g. `gh workflow run <ci>.yml --ref main`), and watch it to green. If it fails, have the owning session fix it forward with a normal PR.
2. Confirm dev deployed and serves that commit (health endpoint, deploy workflow, or the URL the docs give).
3. Tell sessions with deploy-dependent tasks that dev is live at `<commit>`. They run those checks, then archive (rule 6). Wait for every archive PR to merge and every `/safe-to-archive` verdict (rule 10).
4. Promote to production using the project's documented procedure (README/docs "promote"/"production", CLAUDE.md, memory, workflows on a production branch or tag). Note first what's going out, including DB migrations. Do it without asking, unless `--ask-before-prod` was given: then post that list and wait for the user's go. If no procedure is documented, stop and ask.
5. Watch the production deploy to green and verify production serves the new commit. If it's broken, roll back as documented, tell the user, and fix forward.

Release once, after everything is in, not after each merge. With `--stop-after merged`, skip this whole step; with `--stop-after dev`, stop after item 3.

## 8. Final report

Your last message must contain everything:

- **Shipped:** a table with one row per change: PR, archive PR, merged ✅, archived ✅. Then: full CI on main ✅ (run link), dev ✅, and production ✅ (commit, deploy link, URL verified, migrations applied). If an option stopped earlier, say where it stopped and what's left to release.
- **Skipped:** workspaces not in scope, and any session that couldn't be reached.
- **Open decisions: N · Open tests: M**, with a link or pointer to each of those workspaces, and the answers that came back and what you did with them. Don't list the items themselves here.
- **Follow-ups:** anything noticed along the way that isn't a decision or a test (e.g. an unexpected env var). Numbered, one line each.
- **Clean-up:** each workspace's `/safe-to-archive` verdict (✅ safe, or ⛔ with what's left), so the user knows which to archive in Conductor. If `safe-to-archive` isn't installed, say so and list the workspaces whose PRs and archive PRs are merged.

Keep watching Open Decisions and Open Tests after the report, and carry out answers as they come back (step 9). When both reach 0 and every answer is handled, post a last plain-language wrap-up. Then, if `safe-to-archive` is installed, run `/safe-to-archive` in this workspace as your final command.

## 9. Open Decisions and Open Tests

Decisions the user may want to revisit, and tests only the user can do, each go to their own Conductor workspace, so they don't get mixed into this chat's updates. The user works through them in batches, at their own pace.

- **Open Decisions** gets every decision you or a session made on the user's behalf that they might reverse, every "owner review" item from a PR, and any question you left for the user that doesn't block merging. Send each one as soon as it's known.
- **Open Tests** gets every test only the user can do. Send each one once its feature is live where the user can test it (dev or production), not before.
- User setup that blocks merging or the release (secrets, accounts) stays in this chat (step 5).

**Find or create the workspace.** Before sending an item, look for an open workspace of this repo named `Open Decisions` (or `Open Tests`). If there is one, send the item to its session. If there isn't (e.g. the last one was finished and archived), create a new one with the queue prompt below as its first message, then send items to it. Locally, create it the way `new-batch-explore` does (a `conductor://new` link the user confirms with Enter, then the name set in Conductor's database) and tell the user to press Enter. In the cloud, see `cloud.md`. Never stage-rename these two workspaces.

**Queue prompt** (the first message of a new one; fill in this workspace's name):

```
You're the Open <Decisions|Tests> queue for /babysitter, which runs in the workspace "<this workspace's name>". It will send you <decisions the user may want to revisit|tests only the user can do>, each starting with "Via Babysitter:". Don't change code or open PRs yourself: the babysitter carries out the answers.

- Present one item at a time, oldest first. Wait for the user's reply before the next. If new items arrive while one is waiting, queue them.
- The items come from different milestones, so each one stands on its own: start with "<Decision|Test> <n> of <open count>", then the milestone and feature in plain words, the workspace it came from, and what was built and why this is open.
- Always offer skip.
- After each reply, write one line starting "Answered:" (or "Result:") with the item number, the reply, and anything the user added, then present the next item.
- When the last open item is answered, post a short, warm message that makes the user feel good: what they got through, what it unblocked, and that the queue is empty. If more items arrive later, start again.
```

**Each item you send** ("Via Babysitter: add <decision|test>: …") carries everything the queue needs.

For a **decision**:
- the milestone and feature in plain words, and the workspace it came from
- one or two lines of context: what was built and why it's open
- lettered options (a, b, c…), each with its trade-off in a few words, with the current choice marked as such
- one option marked **(recommended)** with a one-line reason
- "skip: keep the current choice"

When the choices aren't a fixed set, still offer the likely answers as options. If there's truly no sensible recommendation, say why. Accept a letter, a letter plus tweaks, or a free answer.

For a **test**: assume the user hasn't followed the build. They don't know the new screens, flags, test data, or what the feature is even called in the UI. Testing is tedious, so every test does two things: (a) gives cohesive, from-scratch instructions, and (b) offers a way to make the test faster and less annoying without making it less thorough.

(a) **How to do it, from scratch.** Write it so someone who never saw the change can follow it top to bottom without guessing:
- the milestone and feature it covers, the workspace it came from, and one or two plain-language lines on what it does for the end user and why it matters
- where to start: a direct link to the exact page (not the home page), the account or role to use, and where its login lives
- setup, already done for them where possible (test data seeded, a flag turned on, a test account created), with anything left for them spelled out, including prerequisites like "the site must be on a paid plan" and how to get there
- numbered steps that name exactly what to click or type and where it is on the page ("in the left sidebar, open **more**, then **add a page**"). Check the real labels and navigation in the code before writing them. Don't guess from the spec, and say so if you couldn't confirm a label.
- what should happen at each check, quoting the exact on-screen text where there is one, and what a failure would look like
- how to clean up afterwards (turn the setting back off, delete test data), if the test leaves anything behind

(b) **A shortcut that keeps it effective.** Offer at least one, ideally both, and say how much time each saves:
- a self-contained prompt they can paste into a browser agent (Claude in Chrome, Codex's browser extension, or similar) that runs the steps from (a) and reports pass/fail with screenshots. Include the URL, account, steps, expected results, clean-up, and what to report back. Never put real passwords in it; use throwaway test values.
- or an offer to have it done for them (headless browser, API calls, curl for status codes and headers, database checks), leaving the user only the part that needs their eyes or their logins. Say exactly which part that is.

End with: reply "pass", "fail: <what happened>", or "skip". On a fail, the queue asks at most one follow-up if it helps pin the bug down (a screenshot, or exactly what they clicked).

**Handle the answers.** Watch both queue sessions like the others (step 4). When one posts "Answered:" or "Result:":
- **Kept, skipped, or passed:** mark it done in the state file.
- **Reversed decision or failed test:** send the fix to the session of the workspace where that work happened, as a normal "Via Babysitter:" brief, and drive it to merge like any other change. Its tests go back to Open Tests once the fix is live. If that workspace is gone or archived, open a follow-up the same way (a new workspace with a self-contained brief), and babysit it.
- Report it in your next update in one plain line, and update the counts.

## Rules

- Never run `login`/`logout` for any CLI and never write secrets to files. Follow the project's account, secrets and browser-profile rules, and pass the relevant ones on to sessions when they matter.
- Don't edit files in other worktrees yourself. The sessions own their workspaces. Exception: a session is gone or unresponsive and the work would otherwise stall. Then do the step from its worktree (`git -C <path>`), log it in that worktree's `.context/babysitter-log.md` starting with `Via Babysitter: ` (tell helper agents to do the same), and say so in the update.
- Don't rename branches, and don't archive Conductor workspaces.
