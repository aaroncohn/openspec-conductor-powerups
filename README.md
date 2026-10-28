# openspec-conductor-powerups

Opinionated [Claude Code](https://claude.com/claude-code) skills for people who build with [OpenSpec](https://openspec.dev) inside [Conductor](https://conductor.build).

Conductor lets you run many coding agents side by side, each in its own workspace. OpenSpec gives each piece of work a plan (explore → propose → apply → archive). These skills handle the parts in between: deciding what to start next, getting everything that's been proposed shipped, and cleaning up afterwards.

| Skill | What it does |
| --- | --- |
| **new-batch-explore** | Reads your roadmap, picks the next 2–5 milestones that can be built in parallel without colliding, and opens a Conductor workspace for each one, already in `/opsx:explore`. |
| **babysitter** | After you've explored and proposed in several workspaces, run this in one more workspace. It messages each workspace's Claude session, answers their questions for you, and keeps them moving until every change is tested, merged, archived, and released to production. If `safe-to-archive` is installed, each workspace runs it last. Then it walks you through the decisions it made, one at a time with a recommendation, and the things only you can test, one at a time with full steps and a shortcut (a prompt for your browser agent, or an offer to do most of it). |
| **safe-to-archive** | Checks whether a workspace can be archived without losing anything: uncommitted or unpushed work, open PRs, stashes, unarchived OpenSpec changes, files that only exist in this workspace, running processes. Read-only. |
| **browser-handoff** | For cloud workspaces: when an agent needs something done in your real browser (a dashboard setting, a secret pasted into a web UI), it writes one self-contained task block, with the exact account and your project's rules, for you to paste into a local `claude --chrome` session. |
| **better-decision** | Before a choice that matters, stops and lays out at least four real options, each with pros, cons, how hard it is to undo, and a rating, then recommends one and waits for your pick. In an OpenSpec change, it records the pick in `design.md`. Use it anytime, in any workspace. |

## The loop

```
/new-batch-explore          → N new workspaces, each exploring one milestone
/opsx:explore, /opsx:propose  in each workspace (that's you, thinking with Claude)
/babysitter                 → apply, test, merge, archive, release (hands off)
/safe-to-archive            in each workspace (babysitter runs it for you) → archive it in Conductor
```

Each skill works in both **local** (Mac) and **cloud** Conductor workspaces. It checks `CONDUCTOR_IS_LOCAL` and, in the cloud, uses the `conductor` CLI in place of things that only exist on your Mac (the `conductor://` link, Conductor's local database). The cloud steps are in each skill's `cloud.md`. See [Local vs cloud](#local-vs-cloud) for what differs.

## Install

In Claude Code:

```
/plugin marketplace add aaroncohn/openspec-conductor-powerups
/plugin install powerups@openspec-conductor-powerups
```

The skills are then `/powerups:babysitter`, `/powerups:new-batch-explore`, and so on.

**Stay on the latest version.** There's no version number: every commit to `main` is a release. Turn on auto-update once and Claude Code picks up new commits in the background after a session starts: in `/plugin`, open **Marketplaces**, pick `openspec-conductor-powerups`, and choose **Enable auto-update**. Or add it to `~/.claude/settings.json`:

```json
"extraKnownMarketplaces": {
  "openspec-conductor-powerups": {
    "source": { "source": "github", "repo": "aaroncohn/openspec-conductor-powerups" },
    "autoUpdate": true
  }
},
"enabledPlugins": { "powerups@openspec-conductor-powerups": true }
```

Without auto-update, run `/plugin marketplace update openspec-conductor-powerups`.

**For cloud workspaces**, a cloud sandbox can't see your Mac's plugins, so install the plugin when each workspace is created. Add the `extraKnownMarketplaces` and `enabledPlugins` entries above to your repo's `.claude/settings.json`, and add this to your Conductor setup script:

```bash
claude plugin marketplace add aaroncohn/openspec-conductor-powerups --scope project && claude plugin install powerups@openspec-conductor-powerups --scope project
```

Every new workspace then gets the latest version.

If you'd rather have short names (`/babysitter`) and update by hand, copy the folders into `~/.claude/skills/` (or your repo's `.claude/skills/` for cloud workspaces) instead:

```bash
git clone https://github.com/aaroncohn/openspec-conductor-powerups
cp -R openspec-conductor-powerups/skills/* ~/.claude/skills/
```

**Upgrading from `openspec-conductor-powerups@openspec-conductor-powerups`:** the plugin is now called `powerups`. Claude Code moves your install over the next time the marketplace updates; if it says the plugin isn't cached, run `/plugin install powerups@openspec-conductor-powerups` once.

## Local vs cloud

Each skill works with the workspaces of its own kind: run from a local workspace, it creates, messages and checks local workspaces; run from a cloud workspace, cloud ones. Keep a batch all local or all cloud.

| | Local (Conductor on your Mac) | Cloud (Conductor cloud workspaces) |
| --- | --- | --- |
| **Install** | The plugin, with auto-update on (see [Install](#install)). | The plugin, installed by your Conductor setup script from the repo's `.claude/settings.json` (see [Install](#install)): a cloud sandbox can't see your Mac's plugins. |
| **Setup** | None. | The `conductor` CLI needs an API token. Turn on automatic API access in Conductor → Settings → General before creating the workspaces (it only applies to new ones), or set `CONDUCTOR_API_KEY`. |
| **new-batch-explore** | Opens Conductor's Create dialog for each workspace; you press Enter once per workspace. Then it names each one `m{id}-{name}` in Conductor's database (backed up first). | Creates and names the workspaces itself, with no clicks, and gives you a link to each. |
| **babysitter** | Messages appear in each workspace's chat, starting with "Via Babysitter:". They go through Conductor's database (backed up first; falls back to Claude Code's `SendMessage` if that stops working). Keep the Conductor app open and the Mac awake. Sessions can use your browser and its logins. | Messages appear in each workspace's chat through the `conductor` CLI. Sessions run in Linux sandboxes, so anything that needs your Mac (your browser and its logins, local files) comes to you as a handoff. |
| **safe-to-archive** | Checks this workspace's branch. Other local branches live in the shared repository and survive archiving. | Archiving deletes the whole sandbox, so it checks every branch in it, plus any running cloud browser session. |

## Requirements and assumptions

These skills are opinionated. They work best if your setup looks like this:

- **Claude Code in Conductor.** Locally, `new-batch-explore` uses Conductor's `conductor://` link to open each workspace and then names it in Conductor's database (backed up first), and `babysitter` messages sessions by queuing them in Conductor's local database (see below). In the cloud, both use the `conductor` CLI, which needs an API token: turn on automatic API access in Conductor → Settings → General, or set `CONDUCTOR_API_KEY`. They won't work with other agents.
- **OpenSpec** with the `/opsx:*` commands installed in the repo.
- **GitHub and the `gh` CLI**, logged in. PRs are squash-merged into `main`.
- **A roadmap file** for `new-batch-explore`: a `roadmap.md` (or similar) on your default branch that lists milestones with IDs, steps, and status (✅ for done, 🟡 for in progress). It skips milestones marked as waiting on someone, and it will ask you where the roadmap is if it can't find one.
- `python3`, plus `sqlite3` locally (both ship with macOS).

### Before you run babysitter

`babysitter` is built to run without you. Know what it will do:

- It answers other sessions' questions **on your behalf**, picking the recommended option. It lists each decision so you can reverse it.
- It **merges PRs into `main`** and, once you say go, **promotes to production** following your repo's documented procedure (README, CLAUDE.md/AGENTS.md, or workflows). If no procedure is documented, it stops and asks.
- It never logs in or out of any CLI and never writes secrets to files. Setup that needs your accounts (secrets, dashboards) is handed to you as step-by-step instructions as soon as it comes up.
- **Locally, it writes to Conductor's own database.** Conductor has no supported way to post a message into another local workspace's chat, so `babysitter` puts its messages in the same queue the app uses when you type one. They show in each workspace's chat starting with "Via Babysitter:", and so do the replies. This is undocumented: it backs up the database before the first message, and if a Conductor update breaks it, it falls back to Claude Code's `SendMessage`, which works but doesn't show in the chat. The Conductor app must be open. In the cloud, it uses the supported `conductor` CLI instead.

It only runs when you type `/babysitter`; Claude won't start it by itself.

To keep a hand on the release, add an option (a flag or plain words both work):

Installed as a plugin, type `/powerups:babysitter` wherever this says `/babysitter`.

| You type | It stops… |
| --- | --- |
| `/babysitter` | once, right before production, to show you what's going out and wait for your go (default) |
| `/babysitter --auto-prod` | never: it goes all the way to production |
| `/babysitter --stop-after dev` | after full CI on `main` and the dev deploy are green; you release to production |
| `/babysitter --stop-after merged` | once every change is merged and archived; no CI run on `main`, no deploys |

You can also name the workspaces or milestones to cover: `/babysitter 2.1 2.3 --auto-prod`.

### What you'll see

- **In Babysitter HQ:** a digest about every hour (or when you ask "what's the latest?"): a one- or two-sentence headline, what's waiting on you, what your product gained in plain words, and what's in progress. It only interrupts sooner when something needs you or something broke. Say "update me every 30 minutes" to change the pace.
- **In a workspace that's waiting on you:** its last message starts with `⚠️ BLOCKED: DECISION NEEDED: …` or `⚠️ BLOCKED: ACTION NEEDED: …`, with options and a recommendation or the steps. If a session stops and the babysitter can't get it going again, it leaves `⚠️ STOPPED (via Babysitter): …` there, saying what it tried and what you can do.
- **On a team:** if your `AGENTS.md`/`CLAUDE.md` names more than one owner, each blocked item and each queue item says who should answer it. Otherwise everything goes to whoever ran `/babysitter`.

## Contributing

Issues and PRs are welcome. If one of these skills does something wrong in your setup, an issue showing what happened is the most useful thing you can send.

## Made by

[Aaron Cohn](https://aaroncohn.com). If these save you time, I'd love to hear about it: open an issue, star the repo, or say hi through my site.

## License

[MIT](LICENSE)
