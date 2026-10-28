# CLAUDE.md

A Claude Code plugin, `powerups`, with opinionated skills for people who use OpenSpec inside Conductor. Mostly solo developers, on local and cloud Conductor workspaces. Public, MIT. See README.md for what each skill does.

## Layout

- `.claude-plugin/plugin.json`: the plugin. `name` is `powerups`. No `version`, on purpose.
- `.claude-plugin/marketplace.json`: the marketplace, `openspec-conductor-powerups`, with one plugin at `./`.
- `skills/<name>/SKILL.md`: one skill each. `cloud.md` beside it holds the cloud steps. `skills/babysitter/conductor-local.py` holds babysitter's local, deterministic steps (scan, send, watch).

## Releases

Every commit to `main` is a release. Users with auto-update get it right away, so `main` must always work. Test before merging.

Never add a `version` to plugin.json. Never rename the plugin (`powerups`) or the marketplace (`openspec-conductor-powerups`) without a `renames` entry in marketplace.json.

## Testing a change

1. `claude plugin validate .` passes. Three warnings are expected: no version, no icon, and this CLAUDE.md not being loaded as plugin context (it's for working on this repo, not for users).
2. Test-install into a throwaway config:
   ```bash
   export CLAUDE_CONFIG_DIR=$(mktemp -d)
   claude plugin marketplace add "$PWD"
   claude plugin install powerups@openspec-conductor-powerups
   ```
3. For a live run, start a session with `claude --plugin-dir .`.
4. If you touched `conductor-local.py`: `python3 -m py_compile skills/babysitter/conductor-local.py`, and keep the asserts in `check_stage()` passing (they run first on `scan`). Add an assert when you change stage logic.

## Local and cloud

Each skill checks `CONDUCTOR_IS_LOCAL`. Locally (`1`) it uses Conductor's SQLite database (`CONDUCTOR_DB_PATH`) and `conductor://` links. In the cloud (`0`) it uses the `conductor` CLI, as written in that skill's `cloud.md`. A change to one side needs the matching change on the other, so both behave the same. Update the README's "Local vs cloud" table too.

Conductor's database is undocumented. Anything that writes to it backs it up first (`sqlite3 "$CONDUCTOR_DB_PATH" ".backup ..."`) and has a fallback when a Conductor update breaks it. Read with `?mode=ro` when you only read.

## Keep the skills generic

No details from any one project: accounts, domains, people, product names. The skills read each user's own `AGENTS.md`/`CLAUDE.md` for project rules. Say "the user" or "the owner", not a name. Don't assume `main`; use `CONDUCTOR_DEFAULT_BRANCH` or `origin/HEAD` where you can.

## Writing skills and the README

- Plain words, short sentences, concrete examples. Write for the reader.
- Skills are prompts: shorter beats longer. Cut what the model would do anyway.
- Deterministic steps (queries, parsing, loops) belong in a script, not prose.
- Skill frontmatter: `description` says what it does and when to use it. Use `disable-model-invocation: true` for skills that should only run when the user types them (babysitter, better-decision).
- A new skill also goes in the README table and, if it changes what the plugin does, in the descriptions in plugin.json and marketplace.json.

## Git

- Commit as `Aaron Cohn <32344260+aaroncohn@users.noreply.github.com>`.
- Commit messages say what changed for the user, starting with the skill when it's one skill (`babysitter: ...`).
- Work on a branch, open a PR, and rebase-merge: one commit per change.
- Ask Aaron before pushing to `main` or merging.
