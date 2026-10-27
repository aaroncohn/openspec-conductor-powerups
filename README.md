# openspec-conductor-powerups

Opinionated [Claude Code](https://claude.com/claude-code) skills for people who build with [OpenSpec](https://openspec.dev) inside [Conductor](https://conductor.build).

Conductor lets you run many coding agents side by side, each in its own workspace. OpenSpec gives each piece of work a plan (explore → propose → apply → archive). These skills handle the parts in between: deciding what to start next, getting everything that's been proposed shipped, and cleaning up afterwards.

| Skill | What it does |
| --- | --- |
| **new-batch-explore** | Reads your roadmap, picks the next 2–5 milestones that can be built in parallel without colliding, and opens a Conductor workspace for each one, already in `/opsx:explore`. |
| **babysitter** | After you've explored and proposed in several workspaces, run this in one more workspace. It messages each workspace's Claude session, answers their questions for you, and keeps them moving until every change is tested, merged, archived, and released to production. Then it walks you through the decisions it made, one at a time with a recommendation, and the things only you can test, one at a time with full steps and a shortcut (a prompt for your browser agent, or an offer to do most of it). |
| **safe-to-archive** | Checks whether a workspace can be archived without losing anything: uncommitted or unpushed work, open PRs, stashes, unarchived OpenSpec changes, files that only exist in this workspace, running processes. Read-only. |

## The loop

```
/new-batch-explore          → N new workspaces, each exploring one milestone
/opsx:explore, /opsx:propose  in each workspace (that's you, thinking with Claude)
/babysitter                 → apply, test, merge, archive, release (hands off)
/safe-to-archive            in each workspace → archive it in Conductor
```

Each skill works in both **local** (Mac) and **cloud** Conductor workspaces. It checks `CONDUCTOR_IS_LOCAL` and, in the cloud, uses the `conductor` CLI in place of things that only exist on your Mac (the `conductor://` link, Conductor's local database, cross-session messaging). The cloud steps are in each skill's `cloud.md`.

## Install

In Claude Code:

```
/plugin marketplace add aaroncohn/openspec-conductor-powerups
/plugin install openspec-conductor-powerups@openspec-conductor-powerups
```

Installed as a plugin, the skills get the plugin's name as a prefix: `/openspec-conductor-powerups:babysitter`, and so on. Run `/plugin marketplace update` to get new versions.

If you'd rather have short names (`/babysitter`), copy the folders instead:

```bash
git clone https://github.com/aaroncohn/openspec-conductor-powerups
cp -R openspec-conductor-powerups/skills/* ~/.claude/skills/
```

Or use [skills.sh](https://skills.sh): `npx skills add aaroncohn/openspec-conductor-powerups`.

**For cloud workspaces**, the skills have to be in the repo, because a cloud sandbox can't see your Mac's `~/.claude/skills/`. Copy the folders into your project's `.claude/skills/` and commit them.

## Requirements and assumptions

These skills are opinionated. They work best if your setup looks like this:

- **Claude Code in Conductor.** Locally, `new-batch-explore` reads Conductor's database and uses its `conductor://` link, and `babysitter` uses Claude Code's agent messaging (`ListAgents`, `SendMessage`). In the cloud, both use the `conductor` CLI, which needs an API token: turn on automatic API access in Conductor → Settings → General, or set `CONDUCTOR_API_KEY`. They won't work with other agents.
- **OpenSpec** with the `/opsx:*` commands installed in the repo.
- **GitHub and the `gh` CLI**, logged in. PRs are squash-merged into `main`.
- **A roadmap file** for `new-batch-explore`: a `roadmap.md` (or similar) on your default branch that lists milestones with IDs, steps, and status (✅ for done, 🟡 for in progress). It skips milestones marked as waiting on someone, and it will ask you where the roadmap is if it can't find one.
- `python3`, plus `sqlite3` locally (both ship with macOS).

### Before you run babysitter

`babysitter` is built to run without you. Know what it will do:

- It answers other sessions' questions **on your behalf**, picking the recommended option. It lists each decision so you can reverse it.
- It **merges PRs into `main`** and **promotes to production** following your repo's documented procedure (README, CLAUDE.md/AGENTS.md, or workflows). If no procedure is documented, it stops and asks.
- It never logs in or out of any CLI and never writes secrets to files. Setup that needs your accounts (secrets, dashboards) is handed to you as step-by-step instructions as soon as it comes up.

It only runs when you type `/babysitter`; Claude won't start it by itself.

To keep a hand on the release, add an option (a flag or plain words both work):

| You type | It stops… |
| --- | --- |
| `/babysitter` | never: it goes all the way to production (default) |
| `/babysitter --ask-before-prod` | once, right before production, to show you what's going out and wait for your go |
| `/babysitter --stop-after dev` | after full CI on `main` and the dev deploy are green; you release to production |
| `/babysitter --stop-after merged` | once every change is merged and archived; no CI run on `main`, no deploys |

You can also name the workspaces or milestones to cover: `/babysitter 2.1 2.3 --ask-before-prod`.

## Contributing

Issues and PRs are welcome. If one of these skills does something wrong in your setup, an issue showing what happened is the most useful thing you can send.

## License

[MIT](LICENSE)
