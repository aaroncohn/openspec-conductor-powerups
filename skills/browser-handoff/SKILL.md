---
name: browser-handoff
description: Write a self-contained handoff block for a browser task that the user's local Claude Code session (connected to their Chrome with `claude --chrome`) will run. Use when an agent in a Conductor cloud workspace needs a setup or admin task done in the user's real browser (a dashboard setting, a secret pasted into a web UI, a check behind their logins), or when the user asks for a handoff block.
---

# browser-handoff

A cloud workspace can't reach the user's browser or its logins. A local Conductor workspace running `claude --chrome` can. Write the task so that agent can do it with nothing but this block and the repo, then hand the block to the user to paste into that session.

## Before you write

Read the project's rules in `AGENTS.md` / `CLAUDE.md` (and any docs they point to) for accounts, secrets, plans and billing, and logging in. Carry the ones that apply to this task into the block. The local agent has the repo but not this conversation, so it can read those docs too: link to them instead of copying long sections.

## Rules

- Spell out every name, ID, URL, value and setting the task needs. Don't write "the project" or "the usual account".
- Name the exact account to use, and have the agent confirm it's signed in as that account before doing anything.
- Never put a secret in the block. If the task needs one, the block says the user pastes it into the service's web UI themselves.
- Don't upgrade a plan, start a trial, or add a payment method unless the project's rules or the user say so. Otherwise the agent stops and asks.
- If the task logs in to the project's own app, say how, following the project's rules for logging in.
- One task per block. If it touches more than one service or would take more than about 15 minutes, split it.
- Fill in every section. Write "none" when a section doesn't apply; don't drop it.

## Format

Output exactly one fenced block, then one line telling the user where to paste it.

````
## browser task: <short name>

**Goal:** <one or two sentences: what should be true when this is done, and why>

**Exact account:** <service> as <account>. Before doing anything, confirm the signed-in
account matches. If it doesn't, stop and report which account is signed in.

**Project rules that apply:** <the rules from AGENTS.md/CLAUDE.md that matter here, one line
each, with the doc they come from; or "none">

**Steps:** <numbered, specific: URLs, menu names, field names, exact values>

**Done when:** <checkable criteria: what to see on which page, which value is saved>

**Don't touch:**
- Don't upgrade a plan, start a trial, or add a payment method (unless the project rules above allow it). Stop and ask instead.
- <anything else out of scope: other projects, environments, settings, existing records>
- Confirm with the user before anything hard to reverse or public.

**Report back:** <exactly what to return: IDs, URLs, values that aren't secret, screenshots
saved to `.context/`, or "done" plus anything unexpected>
````

Paste this into a local Conductor workspace of this repo running `claude --chrome`.
