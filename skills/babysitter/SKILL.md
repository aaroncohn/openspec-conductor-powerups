---
name: babysitter
description: Coordinate every other Conductor workspace of this repo whose OpenSpec change has been proposed, messaging their Claude sessions directly and keeping them moving until each change is built, tested, merged into main with green CI and archived, then promote main to production. Answers their questions on the user's behalf, and sends decisions to revisit, tests only the user can do, and actions only the user can do (secrets, accounts, payment details) to separate Open Decisions, Open Tests and Open Actions workspaces, which present them one at a time. Works in local and cloud Conductor workspaces. Run with /babysitter, optionally followed by the workspaces or milestones to cover, and --auto-prod or --stop-after merged|dev.
disable-model-invocation: true
---

# babysitter

The user has finished `/opsx:explore` and `/opsx:propose` in one or more other Conductor workspaces and wants the features shipped without more involvement. This session is the **coordinator**. Each workspace's own Claude session keeps doing its own work, with its explore context intact. The coordinator sends instructions straight into those sessions, answers their questions on the user's behalf, nudges them when they stall, and owns the steps that span workspaces: CI on main, the production release, and the final report.

Fully autonomous: never wait on the user for anything a session can do or decide. Only actions that need the user's own accounts go to the user (see step 5), and blocking decisions wait for them ("Blocking or batch"); so does production, unless `--auto-prod` was given.

**Who "the user" is.** The person who ran `/babysitter`. If the project names more than one owner (in `AGENTS.md`/`CLAUDE.md`, or in the docs they point to), each `⚠️ BLOCKED` item and each Open Actions, Open Decisions or Open Tests item says who should answer it when that's clear (for example, the owner of that area, or the person who made the original decision). When it isn't clear, it's the person who ran `/babysitter`.

**Local or cloud.** If `CONDUCTOR_IS_LOCAL` is `0`, this is a cloud workspace: the other workspaces run in their own sandboxes, so read `cloud.md` (next to this file) and use it for finding the workspaces (step 1), messaging them (step 3), and watching them (step 4). Everything else is the same.

**Locally**, message sessions with `conductor-local.py` (next to this file), so each message and the session's reply show in that workspace's chat. Claude's own `SendMessage` reaches the session too, but Conductor doesn't record those turns, so the workspace chat stays blank. The script queues messages in Conductor's own outbox, which is undocumented: a Conductor update can break it, so fall back to `SendMessage` when it fails (step 3).

**`main`** below means the repo's default branch: `$CONDUCTOR_DEFAULT_BRANCH` if it's set, otherwise the one `origin/HEAD` points to. `conductor-local.py scan` works it out the same way and prints it as `base`.

## Options

By default the babysitter goes all the way to production, but asks once first: before promoting (step 7.4) it posts what's going out (PRs, database migrations) and waits for the user's go. The user can change that after `/babysitter`, as a flag or in plain words ("don't ask before prod", "stop after dev"):

- `--auto-prod`: promote to production without asking.
- `--stop-after merged`: stop once every change is merged and archived. Skip step 7: no full CI run on `main`, no dev check, no production release. Archive-blocking tasks that need a deployed environment stay open and go in the report.
- `--stop-after dev`: do step 7 up to and including dev (full CI on `main`, dev verified, archives merged), then stop before production.
- How often to post digests (step 6), in plain words, e.g. "update me every 30 minutes". The default is about every hour.

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
/goal Every workspace in .context/babysitter.md has its change merged into main and archived, full CI on main is green after the last merge, the latest main is promoted to production and verified, and the babysitter final report (with the Open Decisions, Open Tests and Open Actions counts) has been posted.
```

## 1. Find the workspaces

If the user named workspaces or milestones after `/babysitter`, cover exactly those. Otherwise detect them:

```bash
git fetch origin -q
python3 <this skill's dir>/conductor-local.py scan    # one JSON line per open workspace of this repo
```

Each line has the workspace's name, path, branch, chat session id and status, its OpenSpec changes that aren't archived on `origin/main`, its PR (the open one, otherwise the newest: number and state), and its stage (see "Stage in the workspace name"). It only reads Conductor's database. If it fails, fall back to `git worktree list --porcelain` and `git ls-tree --name-only origin/main openspec/changes/archive/`, and work these out by hand.

A worktree other than this one is **in scope** when `openspec/changes/` (skip `archive/`, include uncommitted files) has a change that isn't archived on `origin/main`. It's also in scope when it has work that isn't on `origin/main` (uncommitted changes, an open PR, or commits whose content isn't on `origin/main`), or when its session last stopped asking whether to commit, open a PR or merge: drive that work to merge too. Other worktrees are still exploring. Leave them alone and list them as skipped.

The scan gives each worktree's chat session (the tab open in that workspace); for one workspace, `python3 <this skill's dir>/conductor-local.py session <worktree path>` does the same. The session's transcript is the newest `.jsonl` in `~/.claude/projects/<worktree path with every character that isn't a letter or digit replaced by ->/`. Read its last assistant messages to see where it stopped:

```bash
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' <file> | tail -20
```

Before the first message, back up Conductor's database: `sqlite3 "$CONDUCTOR_DB_PATH" ".backup '$HOME/conductor-backups/conductor-<timestamp>.db'"` (make the folder first). Tell the user where the backup is, and that your messages will appear in each workspace's chat starting with "Via Babysitter:".

Then name this workspace `Babysitter HQ`, so the user can find it in the sidebar: the same `sqlite3` update as in "Stage in the workspace name", with this worktree's path.

Then put each workspace's stage in its name (see "Stage in the workspace name"), skipped ones included.

Also learn the repo's conventions before the first message: CI workflows and labels (which checks are quick and which are full, how the full suite is triggered), AGENTS.md / CLAUDE.md / README rules for PRs and commit authors, how past archive PRs looked (`gh pr list --state merged -L 10`), and how dev and production deploy and get verified.

## 2. Keep a state file

`.context/babysitter.md` has one row per change: workspace, session name, branch, change, PR, archive PR, stage (`building → testing → PR open → merged → post-merge checks → archived`), what the session is waiting on, and notes. Also keep every item sent to Open Decisions, Open Tests and Open Actions (step 9) with its status: open, answered, passed, failed, done, or skipped. Update it after every event. After a context compaction, re-read it before acting.

**Times are in the user's timezone.** Every time you write, in this chat, in messages to sessions and queues, in the state file and in logs, is in the user's timezone, 12-hour with the zone's current abbreviation: "7:45 pm EDT", never UTC. Work out the zone once, at the start, and keep its name in the state file (e.g. `America/New_York`):

- **Locally:** the Mac's zone, from `readlink /etc/localtime` (it ends in the name).
- **In the cloud:** the sandbox runs on UTC. Use a timezone the project's `AGENTS.md`/`CLAUDE.md` names. Otherwise ask the user once, in your first message ("What timezone are you in? e.g. New York"), and use UTC, labelled UTC, until they answer.

Get the current time with `TZ=<zone> date '+%-I:%M %p %Z' | sed 's/AM/am/;s/PM/pm/'`. The abbreviation follows daylight saving by itself (EDT in summer, EST in winter).

## Stage in the workspace name

Start each workspace's name with its OpenSpec stage, so the sidebar shows where it is: `explore-`, `propose-`, `apply-` or `archive-` (e.g. `m10-alerts` becomes `apply-m10-alerts`). Set it in step 1 for every workspace of the repo except this one and the Open Decisions, Open Tests and Open Actions workspaces (step 9), and rename again whenever a workspace's stage changes:

| Stage | When |
| --- | --- |
| `explore` | no change that isn't on `origin/main` yet, and no other work that isn't on `origin/main` |
| `propose` | it has a change that isn't on `origin/main` yet, but `openspec status --change <name>` (run in its worktree) isn't planning-complete |
| `apply` | planning is complete, until its PR is merged; or it has work outside `openspec/` that isn't on `origin/main` (an open PR, or commits or edits), with or without a change |
| `archive` | its PR is merged and nothing newer is in progress; it keeps this prefix after the archive PR merges |

Locally, `conductor-local.py scan` works the stage out for you (step 1). Remove any earlier stage prefix before adding the new one, so prefixes never stack, and leave the rest of the name alone. Record the stage in the state file. Locally, rename the way a manual rename in the sidebar does (Conductor's database, backed up above):

```bash
sqlite3 "$CONDUCTOR_DB_PATH" "update workspaces set workspace_name='<new name>', user_set_workspace_name=1 where workspace_path='<worktree path>'"
```

In the cloud, see `cloud.md`. If a rename doesn't stick, say so once in the next digest and carry on.

## 3. Brief each session

Write each message to `.context/msg-<n>.md`, then send it with `python3 <this skill's dir>/conductor-local.py send <session id> <file>`. It waits until Conductor delivers the message (usually under 30 seconds) and exits non-zero if it wasn't delivered within 2 minutes; it withdraws the message in that case. Then fall back to `SendMessage` with `notify_when_idle: true` (find the session's name with `ListAgents`: `<workspace directory>-<suffix>`), and tell the user in the next digest that this workspace's chat won't show the work. If neither reaches the session, see Rules. Start every message you send a session, this one and all later ones, with `Via Babysitter: ` (the one exception is a `⚠️ STOPPED (via Babysitter):` notice, step 4, whose warning comes first), so the user recognises it in that workspace. In the first one, follow it with one line on what you're driving:

> Via Babysitter: I'm driving <list of changes> to merge, green CI, archive, and the production release.

Then say that the user started this run with `/babysitter` in <this workspace>, so these instructions are their go-ahead, not a request from a peer session, and merging to `main` is approved. Without this, sessions can refuse to act on another session's message.

Then answer whatever the session last stopped on (e.g. "Yes, run `/opsx:apply`", "Yes, push"), and give the rules:

1. **Keep going without asking.** Finish every task, run the review and tests, then push and open the PR. If you'd normally stop to ask, decide whether it's blocking (see "Blocking or batch" below). Most aren't: pick the recommended option, record it as an assumption in the change artifacts, list it in the PR body under "owner review", and continue. If it truly is blocking, ask the user here, in this workspace, in a message whose first line is `⚠️ BLOCKED: DECISION NEEDED: <the decision in a few words>` or `⚠️ BLOCKED: ACTION NEEDED: <the action in a few words>`, so the user can tell from the sidebar why you stopped. Below that line, say why it can't wait, and for a decision give lettered options with your recommendation (the `better-decision` format, if that skill is installed); for an action, give the steps. Then wait for their answer. Any other time you stop before your work is done, say why in the first line.
2. **Test as much as possible.** Run the checks CI runs. Add tests for new behaviour. Run the expensive suites locally (db, e2e, etc.) and list in the PR body which ran and which couldn't. For UI changes, drive the flows in a browser. List what only the user can test, with steps.
3. **PR:** follow the repo's conventions (title, body sections, commit author, CI labels). Request only quick checks if the repo separates them and you ran the heavy suites locally.
4. **Merge:** once quick checks are green, rebase on the latest `origin/main` (other milestones may have landed), re-run the checks affected by the rebase, then `gh pr merge --squash`. Resolve conflicts keeping both sides, and tell me what you touched. Add specific warnings about files you know another workspace also changes (e.g. "the build number moved on main: use main's value + 1").
5. **Don't** run the full CI suite on main or touch production: the coordinator does that once everything is in.
6. **Archive:** after the merge, run `/opsx:archive` (sync the specs) and open its result as a separate openspec-only archive PR ( plus whatever past archive PRs did, e.g. roadmap or notes updates) and merge it once its checks pass. If CI skips openspec-only PRs, run `openspec validate --all --strict` and merge it yourself. **Exception:** if some tasks can only be checked against a deployed environment, leave them open, and archive after the coordinator says the deploy is live.
7. **Setup only the user can do** (secrets, dashboard settings, third-party accounts): don't block on it unless it's truly blocking (see below). Make sure nothing hard-fails without it, put the steps in the PR body under "owner setup", and tell me right away.
8. Reply with the PR URL(s) when merged.
9. **Log:** after each step (tasks done, tests run, PR opened, merged, archived) and each decision you made without asking, add a line, dated in the user's timezone (<the zone, e.g. `America/New_York`>), to `.context/babysitter-log.md` in your workspace, with PR links.
10. **Last:** once the archive PR is merged, if the `safe-to-archive` skill is installed (in your skill list as `safe-to-archive`, or `powerups:safe-to-archive` as a plugin), run `/safe-to-archive` as your final command. Fix any blocker that's your own work (e.g. commit and push), run it again, and reply with its verdict. Don't archive the workspace.

## 4. Watch and keep them moving

- Run `python3 <this skill's dir>/conductor-local.py watch <session id> ...` in the background (Bash `run_in_background`) for every session still in flight. It exits, naming the session, when one finishes a turn. Then read the end of its transcript, check its PR (`gh pr view <n> --json state,mergeStateStatus,statusCheckRollup`), act, and start the watcher again. For a session on the `SendMessage` fallback, `notify_when_idle` does this job; it's one-shot, so subscribe again with each reply.
- **It asked something:** first decide whether it's blocking ("Blocking or batch" below). If not, answer as the user would: the recommended option, recorded as an assumption. Then add it to Open Decisions (step 9) so the user can review it later, and mention it in the next digest. If it is blocking, check that the session's last message starts with the `⚠️ BLOCKED:` line (rule 1). If it doesn't, tell it to post one now and wait. Then tell the user right away in this chat (step 6), and keep it under **Waiting on you** until it's answered.
- **It stopped and you can't tell why** (no `⚠️ BLOCKED:` line, no question, work not done; e.g. a long test run finished but it never woke up to read it): prod it once to check where it is and continue, or, if it's waiting on the user, to post its `⚠️ BLOCKED:` line. If it still hasn't moved by the next re-scan, or it's erroring, send `⚠️ STOPPED (via Babysitter): <what it was doing>. <what you tried>. <what the user can do, e.g. open the workspace and press continue, or restart the session>` to that workspace, so that's the last thing the user sees there, and put it under **Waiting on you** (step 6).
- **Stay on the latest `main`:** after every merge into `main` (a change or an archive PR), update this workspace: `git fetch origin -q` and `git merge --ff-only origin/main` (or `git pull --ff-only`). You never commit here, so it should fast-forward; if it can't, check out `origin/main` detached instead. Read specs, the roadmap and code from this up-to-date copy.
- **Overlap:** when one change lands, tell the remaining sessions what moved on `main` that touches their files.
- **A session that won't take messages** (the notice says the subscription expired, or a delivery notice says messages are held for approval): tell the user right away, as for a `⚠️ STOPPED` workspace (step 6), and keep the others moving.
- **Re-scan every 10 minutes.** Run the watcher with a 10-minute background timeout (Bash `timeout: 600000`), so you're woken even when no watched session finishes a turn. After every wake-up, redo step 1's scan for every workspace of the repo, then:
  - rename any workspace whose stage changed ("Stage in the workspace name");
  - adopt any workspace that has newly come into scope (for example, the user just ran `/opsx:propose` or `/opsx:apply` there). Brief its session (step 3), add it to the watcher, and mention it in the next digest: "Babysitter took over <workspace name> to keep it moving. You can tell me to stop babysitting it at any time."

  If nothing changed, or nothing worth posting right away (step 6), restart the watcher without posting.
- **Stop babysitting:** when the user says to stop babysitting a workspace, stop messaging and watching it, mark it `stopped by user` in the state file, and don't adopt it again on a re-scan unless the user asks. Confirm in one line.
- Don't poll in a loop yourself. Between events, end the turn quietly (step 6). For PR checks you're waiting on, `gh pr checks <n> --watch` is fine.

## Blocking or batch

The goal is speed without lowering quality. So most decisions and actions don't stop the work: the recommended option is taken now and the user reviews it later, in batches. Only a few are blocking.

**Blocking** means getting it wrong would change what gets built in a way that's costly to undo, so it has to be settled before the work goes on. Examples:
- a decision about scope, the data model or a migration, pricing or money, security or privacy, or something users will see that's hard to change once it ships
- an action without which the work can't be built or tested at all, with no safe stand-in (a stub, a test key, a feature flag)

**Batch** is everything else: copy, naming, small UX choices, defaults that are easy to change later, follow-ups, and actions the work can ship without (it degrades gracefully until they're done). Batch items go to Open Decisions or Open Actions (step 9), and any change they lead to goes in a future PR.

When unsure, prefer batch if the choice can be reversed in a small later PR; otherwise blocking. A blocking item stays in the workspace where it came up: its session asks the user there, under a `⚠️ BLOCKED:` first line (step 3, rule 1), and waits, while the other workspaces keep going. Record each blocking item in the state file with its workspace.

## 5. User actions: send them to Open Actions as soon as they're known

When a session reports something only the user can do that isn't a decision or a test (an environment variable or secret to set, an account to create, a payment method to add, a dashboard setting, a DNS record), don't save it for the end. If it's blocking ("Blocking or batch"), it stays in that workspace under its `⚠️ BLOCKED:` line and you tell the user right away (step 6). Otherwise send it to Open Actions (step 9) right away. Plan the production release so it waits for actions production needs, or confirm that nothing breaks without them.

## 6. Updates in this chat

The user wants signal, not a build log. Post in this chat only at these moments, and stay quiet otherwise: end the turn without posting, or with a single line if the harness needs one.

**Right away**, in two or three plain lines, when:
- a new blocking decision or action comes up: what it is, why it holds things up, and the workspace to answer it in (where its `⚠️ BLOCKED:` message is waiting)
- a workspace is `⚠️ STOPPED` (step 4)
- something broke that the user would want to know about now: full CI on `main` fails, a deploy fails, production is rolled back
- production is ready to go and needs the user's go (step 7.4)

Everything else (a test passing, a PR opened, a merge, an archive, an adopted workspace, an answer from a queue) waits for the next digest.

**Digests**, as if the user walked into the room and asked "what's the latest on all this?". Post one when the user asks, and otherwise about every hour (or at whatever interval the user asked for) if something changed since the last one. Note the time of each in the state file. If nothing changed, skip it. Shape:

- **The headline:** one or two sentences, e.g. "**3 of 5 merged.** Contact forms and the new sign-in are live on dev; the custom domains work is in review and should merge within the hour."
- **Waiting on you:** one line per open blocking item or `⚠️ STOPPED` workspace, with the workspace to go to. Leave it out when there are none.
- **What your product gained:** a bullet for each feature that merged or went live since the last digest, written as what users can now do and why it's better, in plain, warm words, e.g. "Visitors can message you from your site. Suspicious messages get a quick human check instead of landing in your inbox (#191)." This is the part the user reads to feel the progress, so make it concrete and give each one its due.
- **In progress:** one line per active workspace: the feature in words, where it is, what's next, and a rough time.
- **Open actions: K · Open decisions: N · Open tests: M**, the counts in those three workspaces (step 9), plus one line on any answer that came back and what you did with it.
- End with "**Next:** <the one thing the user should do>" or "Nothing needed from you. Next digest around <time>, if anything changes." (e.g. "around 7:45 pm EDT, if anything changes")

**Plain words everywhere:** name each feature in words, not just its roadmap ID ("2.2b, the spam check"). Leave out test counts, file names, task numbers, CI job names and internal labels unless something failed or the user has to act on them; then say what it means for the user. Don't invent codes like "C1"; describe the item.

**The workspace table** (one row per open workspace of this repo except this one and the three queues, from a fresh scan: workspace name, stage, progress, and a narrow "babysitter monitoring?" column with `x` for the ones you're babysitting) goes in a digest only when the user asks for it, plus in the first message and the final report.

Decisions you made for the user, tests only they can do, and actions only they can do don't go here: they go to Open Decisions, Open Tests and Open Actions (step 9).

## 7. After the last merge: CI on main, dev, production

1. Run the repo's full CI suite on `main` once, the way the repo does it (e.g. `gh workflow run <ci>.yml --ref main`), and watch it to green. If it fails, have the owning session fix it forward with a normal PR.
2. Confirm dev deployed and serves that commit (health endpoint, deploy workflow, or the URL the docs give).
3. Tell sessions with deploy-dependent tasks that dev is live at `<commit>`. They run those checks, then archive (rule 6). Wait for every archive PR to merge and every `/safe-to-archive` verdict (rule 10).
4. Promote to production using the project's documented procedure (README/docs "promote"/"production", CLAUDE.md, memory, workflows on a production branch or tag). Note first what's going out, including DB migrations. Post that list and wait for the user's go, unless `--auto-prod` was given: then do it without asking. If no procedure is documented, stop and ask.
5. Watch the production deploy to green and verify production serves the new commit. If it's broken, roll back as documented, tell the user, and fix forward.

Release once, after everything is in, not after each merge. With `--stop-after merged`, skip this whole step; with `--stop-after dev`, stop after item 3.

## 8. Final report

Your last message must contain everything:

- **Shipped:** a table with one row per change: PR, archive PR, merged ✅, archived ✅. Then: full CI on main ✅ (run link), dev ✅, and production ✅ (commit, deploy link, URL verified, migrations applied). If an option stopped earlier, say where it stopped and what's left to release.
- **Skipped:** workspaces not in scope, and any session that couldn't be reached.
- **Open actions: K · Open decisions: N · Open tests: M**, with a link or pointer to each of those workspaces, and the answers that came back and what you did with them. Don't list the items themselves here.
- **Follow-ups:** anything noticed along the way that isn't a decision or a test (e.g. an unexpected env var). Numbered, one line each.
- **Clean-up:** each workspace's `/safe-to-archive` verdict (✅ safe, or ⛔ with what's left), so the user knows which to archive in Conductor. If `safe-to-archive` isn't installed, say so and list the workspaces whose PRs and archive PRs are merged.

Keep watching Open Actions, Open Decisions and Open Tests after the report, and carry out answers as they come back (step 9). When all three reach 0 and every answer is handled, post a last plain-language wrap-up. Then, if `safe-to-archive` is installed, run `/safe-to-archive` in this workspace as your final command.

## 9. Open Actions, Open Decisions and Open Tests

Actions only the user can do, decisions the user may want to revisit, and tests only the user can do each go to their own Conductor workspace, so they don't get mixed into this chat's updates. The user works through them in batches, at their own pace.

- **Open Decisions** gets every decision you or a session made on the user's behalf that they might reverse, every "owner review" item from a PR, and any question you left for the user, as long as it's batch, not blocking ("Blocking or batch"). Send each one as soon as it's known.
- **Open Tests** gets every test only the user can do. Send each one once its feature is live where the user can test it (dev or production), not before.
- **Open Actions** gets every action only the user can do that isn't a decision or a test (step 5): secrets and environment variables, accounts, payment methods, dashboard settings, DNS, as long as it's batch, not blocking. Send each one as soon as it's known. Ones the release waits on go first.

**Find or create the workspace.** Before sending an item, look for an open workspace of this repo named `Open Actions`, `Open Decisions` or `Open Tests`. If there is one, send the item to its session. If there isn't (e.g. the last one was finished and archived), create a new one with the queue prompt below as its first message, then send items to it. Locally, create it the way `new-batch-explore` does (a `conductor://new` link the user confirms with Enter, then the name set in Conductor's database) and tell the user to press Enter. In the cloud, see `cloud.md`. Never stage-rename these three workspaces.

**Queue prompt** (the first message of a new one; fill in this workspace's name):

```
You're the Open <Actions|Decisions|Tests> queue for /babysitter, which runs in the workspace "<this workspace's name>". It will send you <actions only the user can do|decisions the user may want to revisit|tests only the user can do>, each starting with "Via Babysitter:". Don't change code or open PRs yourself: the babysitter carries out the answers.

- Present one item at a time, oldest first. Wait for the user's reply before the next. If new items arrive while one is waiting, queue them.
- The items come from different milestones, so each one stands on its own: start with "<Action|Decision|Test> <n> of <open count>", then the milestone and feature in plain words, the workspace it came from, and what was built and why this is open.
- Always offer skip.
- After each reply, write one line starting "Done:" (actions), "Answered:" (decisions) or "Result:" (tests) with the item number, the reply, and anything the user added, then present the next item.
- When the last open item is answered, post a short, warm message that makes the user feel good: what they got through, what it unblocked, and that the queue is empty. If more items arrive later, start again.
```

**Each item you send** ("Via Babysitter: add <action|decision|test>: …") carries everything the queue needs.

For an **action**:
- the milestone and feature in plain words, the workspace it came from, and whether it holds up a merge or the release
- why it's needed and what happens until it's done (e.g. "until then, suspicious messages keep going to possible spam")
- directions from scratch: the exact service and account (and to confirm the signed-in account first), a direct link to the right page, numbered steps naming what to click, and what "done" looks like
- the project's rules that apply (e.g. paste secrets into the service's web UI, never into chat; stay on free plans unless the user says otherwise)
- when a browser can do most of it, a self-contained prompt to paste into a browser agent (Claude in Chrome or similar), with goal, exact account, steps, done-when, don't-touch and report-back (if the `browser-handoff` skill is installed, write it with that skill). Never put passwords or secrets in it.
- what to reply when done: "done", plus anything the babysitter needs back (e.g. a public key or ID, never a secret), or "skip"

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
- a self-contained prompt they can paste into a browser agent (Claude in Chrome, Codex's browser extension, or similar) that runs the steps from (a) and reports pass/fail with screenshots. Include the URL, account, steps, expected results, clean-up, and what to report back. Never put real passwords in it; use throwaway test values. If the `browser-handoff` skill is installed, write it with that skill.
- or an offer to have it done for them (headless browser, API calls, curl for status codes and headers, database checks), leaving the user only the part that needs their eyes or their logins. Say exactly which part that is.

End with: reply "pass", "fail: <what happened>", or "skip". On a fail, the queue asks at most one follow-up if it helps pin the bug down (a screenshot, or exactly what they clicked).

**Handle the answers.** Watch the queue sessions like the others (step 4). When one posts "Done:", "Answered:" or "Result:":
- **Action done:** check it took effect where you can (the variable is listed, the deploy picks it up, the page responds), mark it done, and continue whatever was waiting on it. If it didn't take effect, send a follow-up action saying what's still missing.
- **Kept, skipped, or passed:** mark it done in the state file. A skipped action that holds up the release stays under **Waiting on you** in the digests.
- **Reversed decision or failed test:** send the fix to the session of the workspace where that work happened, as a normal "Via Babysitter:" brief, and drive it to merge like any other change. Its tests go back to Open Tests once the fix is live. If that workspace is gone or archived, open a follow-up the same way (a new workspace with a self-contained brief), and babysit it.
- Report it in the next digest, and update the counts.

## Rules

- Never run `login`/`logout` for any CLI and never write secrets to files. Follow the project's account, secrets and browser-profile rules, and pass the relevant ones on to sessions when they matter.
- Don't edit files in other worktrees yourself. The sessions own their workspaces. Exception: a session is gone or unresponsive and the work would otherwise stall. Then do the step from its worktree (`git -C <path>`), log it in that worktree's `.context/babysitter-log.md` starting with `Via Babysitter: ` (tell helper agents to do the same), and say so in the next digest.
- Don't rename branches, and don't archive Conductor workspaces.
