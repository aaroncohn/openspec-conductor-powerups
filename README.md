# babysitter

Opinionated [Claude Code](https://claude.com/claude-code) skills for people who build with [OpenSpec](https://openspec.dev) inside [Conductor](https://conductor.build).

Conductor lets you run many coding agents side by side, each in its own workspace. OpenSpec gives each piece of work a plan (explore → propose → apply → archive). These skills handle the parts in between: deciding what to start next, getting everything that's been proposed shipped, and cleaning up afterwards.

| Skill | What it does |
| --- | --- |
| **new-batch-explore** | Reads your roadmap, picks the next 2–5 milestones that can be built in parallel without colliding, and opens a Conductor workspace for each one, already in `/opsx:explore`. |
| **hq** | After you've explored and proposed in several workspaces, run this in one more workspace. It messages each workspace's Claude session, answers their questions for you, and keeps them moving until every change is tested, merged, archived, and released to production. If `safe-to-archive` is installed, each workspace runs it last. Then it walks you through the decisions it made, one at a time with a recommendation, and the things only you can test, one at a time with full steps and a shortcut (a prompt for your browser agent, or an offer to do most of it). Every item has an ID (`OA001`, `OD001`, `OT001`…) that stays the same everywhere. |
| **pause** | Run it in Babysitter HQ to stop for now. HQ goes silent, and it tells each session it's driving to finish its current step, then not merge or start anything new. The Open Actions, Decisions and Tests workspaces keep working. Anywhere else, it does nothing. |
| **keep-going** | Run it in Babysitter HQ to pick up where pause left off. It catches up on what happened, including your queue answers, tells the held sessions to carry on, and posts a digest. Anywhere else, it does nothing. |
| **status-check** | Where things stand, from wherever you run it. In Babysitter HQ, a full digest with the table. In an Open Actions, Decisions or Tests workspace, how many items are open, by ID with a line each. In any other workspace, its stage, PR and checks, and what's left before merge. |
| **doctor** | Am I on the latest version, and can babysitter work here? Compares the installed plugin and this session's copy with the latest release; checks `gh`, `openspec`, your `## babysitter` defaults, Conductor's database (local) or the `conductor` CLI token and stale workspaces (cloud). Read-only, with a fix per ⛔. |
| **safe-to-archive** | Checks whether a workspace can be archived without losing anything: uncommitted or unpushed work, open PRs, stashes, unarchived OpenSpec changes, files that only exist in this workspace, running processes. Read-only. |
| **browser-handoff** | For cloud workspaces: when an agent needs something done in your real browser (a dashboard setting, a secret pasted into a web UI), it writes one self-contained task block, with the exact account and your project's rules, for you to paste into a local `claude --chrome` session. |
| **better-decision** | Before a choice that matters, stops and lays out at least four real options, each with pros, cons, how hard it is to undo, and a rating, then recommends one and waits for your pick. In an OpenSpec change, it records the pick in `design.md`. Use it anytime, in any workspace. |

## The loop

```
/babysitter:new-batch-explore   → N new workspaces, each exploring one milestone
/opsx:explore, /opsx:propose      in each workspace (that's you, thinking with Claude)
/babysitter:hq                  → apply, test, merge, archive, release (hands off)
/babysitter:pause, /babysitter:keep-going   in Babysitter HQ → hold everything, then carry on
/babysitter:status-check          in any workspace → where things stand
/babysitter:doctor                am I on the latest version, can babysitter work here?
/babysitter:safe-to-archive       in each workspace (babysitter runs it for you) → archive it in Conductor
```

Each skill works in both **local** (Mac) and **cloud** Conductor workspaces. It checks `CONDUCTOR_IS_LOCAL` and, in the cloud, uses the `conductor` CLI in place of things that only exist on your Mac (the `conductor://` link, Conductor's local database). The cloud steps are in each skill's `cloud.md`. See [Local vs cloud](#local-vs-cloud) for what differs.

## Install

In Claude Code:

```
/plugin marketplace add aaroncohn/babysitter
/plugin install babysitter@babysitter
```

The skills are then `/babysitter:hq`, `/babysitter:new-batch-explore`, and so on.

**Stay on the latest version.** There's no version number: every commit to `main` is a release. Turn on auto-update once and Claude Code picks up new commits in the background after a session starts: in `/plugin`, open **Marketplaces**, pick `babysitter`, and choose **Enable auto-update**. Or add it to `~/.claude/settings.json`:

```json
"extraKnownMarketplaces": {
  "babysitter": {
    "source": { "source": "github", "repo": "aaroncohn/babysitter" },
    "autoUpdate": true
  }
},
"enabledPlugins": { "babysitter@babysitter": true }
```

A session that's already open keeps the version it loaded, so after an update run `/reload-plugins` in it or start a new one. To update right now, or without auto-update: `claude plugin marketplace update babysitter && claude plugin update babysitter@babysitter`. `/babysitter:doctor` tells you if you're behind.

**For cloud workspaces**, a cloud sandbox can't see your Mac's plugins, so install the plugin when each workspace is created. Add the `extraKnownMarketplaces` and `enabledPlugins` entries above to your repo's `.claude/settings.json`, and put this in the repository's **Setup script in your organization's cloud settings** (Conductor: switch to the cloud organization at the top left, open the Cloud Computer / organization settings, the repository, Setup script):

```bash
claude plugin marketplace add aaroncohn/babysitter --scope project && claude plugin install babysitter@babysitter --scope project
```

Cloud workspaces don't run the `[scripts] setup` in `.conductor/settings.toml`; that one is local-only ([Conductor's docs](https://www.conductor.build/docs/cloud/environment-variables): "Cloud workspaces run the repository's Setup script from organization settings"). A `SessionStart` hook that runs the same install is a good backup, but it lands after the first session's command list is built: the picker may not list `/babysitter:` for the first few sessions; typing the full name works meanwhile. Every new workspace then gets the latest version.

## Local vs cloud

Each skill works with the workspaces of its own kind: run from a local workspace, it creates, messages and checks local workspaces; run from a cloud workspace, cloud ones. Keep a batch all local or all cloud.

| | Local (Conductor on your Mac) | Cloud (Conductor cloud workspaces) |
| --- | --- | --- |
| **Install** | The plugin, with auto-update on (see [Install](#install)). | The plugin, installed by the repository's Setup script in your organization's cloud settings, from the repo's `.claude/settings.json` (see [Install](#install)): a cloud sandbox can't see your Mac's plugins, and `.conductor/settings.toml`'s setup is local-only. |
| **Setup** | None. | The `conductor` CLI needs an API token. Turn on automatic API access in Conductor → Settings → General before creating the workspaces (it only applies to new ones), or set `CONDUCTOR_API_KEY`. |
| **new-batch-explore** | Opens Conductor's Create dialog for each workspace; you press Enter once per workspace, after checking it says Local and your repo (the link picks your repo, but the dialog opens in whichever organization the switcher is on). Then it names each one `m{id}-{name}` in Conductor's database (backed up first). | Creates and names the workspaces itself, with no clicks, and gives you a link to each. |
| **hq** | Messages appear in each workspace's chat, starting with "Via Babysitter:". They go through Conductor's database (backed up first; falls back to Claude Code's `SendMessage` if that stops working; `/babysitter:doctor --send-test` tells you which). Keep the Conductor app open and the Mac awake, and the organization switcher (top left) on the organization that shows this repo, or the Create dialogs for the queue workspaces make cloud workspaces on another repo. Sessions can use your browser and its logins. | Messages appear in each workspace's chat through the `conductor` CLI. Sessions run in Linux sandboxes, so anything that needs your Mac (your browser and its logins, local files) comes to you as a handoff. |
| **hq's watcher and re-scan** | `conductor-local.py watch` and `scan` read each workspace's stage from its worktree, and its new turns and typed `/opsx:` commands from Conductor's database. | `watch.py` reads `lastActivityAt` and the newest messages through the `conductor` CLI, which doesn't know stages, so they come from the messages, typed `/opsx:` commands included. |
| **pause, keep-going** | Hold and release messages go through Conductor's database, like babysitter's others. | Hold and release messages go through the `conductor` CLI. |
| **status-check** | Same everywhere: it reads this chat, the state file, `gh` and `openspec`. | Same. |
| **doctor** | Checks Conductor's database and the outbox table babysitter writes to. | Checks the `conductor` CLI token, and names workspaces created before the latest release (they may be on an older version). |
| **safe-to-archive** | Checks this workspace's branch. Other local branches live in the shared repository and survive archiving. | Archiving deletes the whole sandbox, so it checks every branch in it, plus any running cloud browser session. |

## Requirements and assumptions

These skills are opinionated. They work best if your setup looks like this:

- **Claude Code in Conductor.** Locally, `new-batch-explore` uses Conductor's `conductor://` link to open each workspace and then names it in Conductor's database (backed up first), and `babysitter` messages sessions by queuing them in Conductor's local database (see below). In the cloud, both use the `conductor` CLI, which needs an API token: turn on automatic API access in Conductor → Settings → General, or set `CONDUCTOR_API_KEY`. They won't work with other agents.
- **OpenSpec** with the `/opsx:*` commands installed in the repo.
- **GitHub and the `gh` CLI**, logged in. PRs are squash-merged into `main`.
- **A roadmap file** for `new-batch-explore`: a `roadmap.md` (or similar) on your default branch that lists milestones with IDs, steps, and status (✅ for done, 🟡 for in progress). It skips milestones marked as waiting on someone, and it will ask you where the roadmap is if it can't find one.
- `python3`, plus `sqlite3` locally (both ship with macOS).

### Before you run babysitter

Babysitter is built to run without you. Know what it will do:

- It answers other sessions' questions **on your behalf**, picking the recommended option. It lists each decision so you can reverse it.
- It keeps the big things first. Small, easily reversed items never hold up a merge or a release; they're graded `minor` and come last in the queues, after anything release-blocking.
- When a session stops to ask for a "go" ("shall I push?", "say go when ready"), it gives the go for you. If a session is waiting for something to finish first (CI, a deploy, a setting you had to change), it watches that and tells the session the moment it's ready. The one go it never gives for you is production, unless you asked for that.
- It re-reads every open workspace of the repo each time it wakes, before it does anything, including before every digest and every `/babysitter:status-check`. Its scan flags each workspace where you typed `/opsx:propose` (or `/opsx:ff`, `/opsx:continue`, `/opsx:apply`) and it isn't driving yet, and it takes each one over before it posts, even mid-proposal or while you're working there yourself; your own messages there still win. It also catches a proposal you started without the command: the session offered to start `/opsx:propose` and you replied "yes", or the session says `/opsx:apply` is next. It reads those and decides. In the cloud, its stages come from each workspace's newest messages, never from its own notes.
- **Merges go one at a time, through a merge lock HQ runs, in overlap order.** Sessions build, test and open PRs in parallel. When one is ready it says so and waits; HQ gives the go to one at a time, the change others overlap with first, so nobody tests against a `main` that another merge then changes. A holder that hasn't merged after 45 minutes gets one prod, then loses its turn. The digest's table shows the line. Archive PRs don't wait.
- It **merges PRs into `main`** and, once you say go, **promotes to production** following your repo's documented procedure (README, CLAUDE.md/AGENTS.md, or workflows). If no procedure is documented, it stops and asks.
- It never logs in or out of any CLI and never writes secrets to files. Setup that needs your accounts (secrets, dashboards) is handed to you as step-by-step instructions as soon as it comes up.
- **Locally, it writes to Conductor's own database.** Conductor has no supported way to post a message into another local workspace's chat, so babysitter puts its messages in the same queue the app uses when you type one. They show in each workspace's chat starting with "Via Babysitter:", and so do the replies. This is undocumented: it backs up the database before the first message, and if a Conductor update breaks it, it falls back to Claude Code's `SendMessage`, which works but doesn't show in the chat. The Conductor app must be open. In the cloud, it uses the supported `conductor` CLI instead.

- **One Babysitter HQ per repo.** Conductor will let you create a second workspace, but `/babysitter:hq` won't start in it while another `Babysitter HQ` is open for the repo, paused ones included. It tells you where the open one is. It can't see an HQ you renamed, or a local HQ from the cloud and the other way round; in the cloud, it only looks at your own workspaces.
- **Pausing holds, it doesn't cancel.** `/babysitter:pause` reaches each session as soon as Conductor delivers the message, so a merge already underway can still land, and a CI run or deploy already running keeps going. It tells you what's still in flight.

It only runs when you type `/babysitter:hq`; Claude won't start it by itself.

To keep a hand on the release, add an option (a flag or plain words both work):

| You type | It stops… |
| --- | --- |
| `/babysitter:hq` | once, right before production, to show you what's going out and wait for your go (default) |
| `/babysitter:hq --auto-prod` | never: it goes all the way to production |
| `/babysitter:hq --stop-after dev` | after full CI on `main` and the dev deploy are green; you release to production |
| `/babysitter:hq --stop-after merged` | once every change is merged and archived; no CI run on `main`, no deploys |

You can also name the workspaces or milestones to cover: `/babysitter:hq 2.1 2.3 --auto-prod`, and set the pace in plain words ("release once a day", "update me every 15 minutes"). By default it releases at most twice a day, even when you add workspaces mid-run. A `## babysitter` section in your `AGENTS.md`/`CLAUDE.md` can hold these defaults for every run (`mode: fast`, `stop after: dev`, `release: once a day`, `Timezone: America/New_York`).

**Mode.** The first time babysitter runs in a repo it asks how much to do on its own, and how often you want digests (every 30 minutes by default; 15 minutes, an hour, or only when something changes), and offers to save the answers to your `## babysitter` section. Pass `--mode <name>` to set it for one run.

| Mode | It decides alone | It asks you about | Releases |
| --- | --- | --- | --- |
| `cautious` | small, easily reversed choices | every merge to `main`, production, anything hard to reverse | once a day at most |
| `standard` (default) | everything except scope, data model and migrations, money, security and privacy, things users see that are hard to change | those, plus production (once) | twice a day at most |
| `fast` | everything except money, security and privacy, data loss, migrations | those; production goes out without asking | whenever something's ready |
| `hyperspeed` | everything except money, security and privacy, irreversible data loss; it logs every call to Open Decisions | those only | whenever something's ready; wrap-up runs alongside the release |


### What you'll see

- **In Babysitter HQ:** a digest every 30 minutes, on the clock, and whenever you ask ("what's the latest?" or `/babysitter:status-check`): what just got done, in plain words about what your product gained; what's waiting on you; what each workspace is working on now; the critical path to the next release and what's holding it up; the open actions, decisions and tests by ID (`OA001`, `OD001`, `OT001` and up, so "Open decisions: 5 (OD005, OD016, OD021, OD027, OD031)"); how long each one should take and when the whole batch should be merged and released; a table of every workspace with its stage, effort (S to XL), progress, next step and ETA; and when the next digest is due. A quiet half hour still gets its digest, one line plus the table, also when nothing is building. Each digest starts from a script that prints its whole shape, so it stays the same hours into a run. Between digests it stays silent, unless something needs you or something broke. Say "update me every 15 minutes" (or "every hour", or "only when something changes" for the cheapest run: no quiet digests, `/babysitter:status-check` whenever you want the table) to change the pace. Times are in your timezone ("7:45 pm EDT"); in a cloud workspace it asks once, unless your `AGENTS.md`/`CLAUDE.md` names one (e.g. `Timezone: America/New_York`).
- **In a workspace that's waiting on you:** its last message starts with `⚠️ BLOCKED: DECISION NEEDED: …` or `⚠️ BLOCKED: ACTION NEEDED: …`, with options and a recommendation or the steps. If a session stops and the babysitter can't get it going again, it leaves `⚠️ STOPPED (via Babysitter): …` there, saying what it tried and what you can do.
- **On a team:** if your `AGENTS.md`/`CLAUDE.md` names more than one owner, each blocked item and each queue item says who should answer it. Otherwise everything goes to whoever ran `/babysitter:hq`.

## Contributing

Issues and PRs are welcome. If one of these skills does something wrong in your setup, an issue showing what happened is the most useful thing you can send.

## Made by

[Aaron Cohn](https://aaroncohn.com). If these save you time, I'd love to hear about it: open an issue, star the repo, or say hi through my site.

## License

[MIT](LICENSE)
