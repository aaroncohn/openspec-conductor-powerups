# new-batch-explore in a Conductor cloud workspace

Read this when `CONDUCTOR_IS_LOCAL` is `0`. There's no Conductor database or `conductor://` link in a cloud sandbox; the `conductor` CLI (on the `PATH`) lists and creates workspaces instead. These sections replace steps 2, 4 and 5 of `SKILL.md`.

If `conductor` fails with an auth error, tell the user that the workspace has no API token: they can turn on automatic API access in Conductor → Settings → General (it applies to new workspaces) or set their own `CONDUCTOR_API_KEY`. Stop until it works.

## 2. Find what's already in flight

```bash
REPO=$(basename -s .git "$(git remote get-url origin)")
conductor workspace list --repo "$REPO" --json --limit 100    # page with --offset while hasMore
```

The output is `{"data": [...], "hasMore": ...}`; each workspace has `id`, `name`, `state` and `lastActivityAt`, but no branch. Archived workspaces aren't listed. Names aren't enough, so for each workspace also read the first message of its sessions, which names its milestone, and its status:

```bash
conductor workspace session <workspaceId> --json                       # its sessions
conductor session message <sessionId> --json --limit 1                 # the first message
conductor --json session status <sessionId>
```

A milestone is **in flight** if a workspace's name, branch or first message mentions it, or an unarchived `openspec/changes/*` on `origin/$BASE` or on a workspace's pushed branch covers it. Working or idle doesn't matter: an idle workspace waiting on a decision is still in progress.

## 4. Create the workspaces

Name each workspace `m{id}-{short-name}`, following the rules in `SKILL.md`. The CLI sets the name directly. The prompt is the same as in `SKILL.md`:

```
/opsx:explore Milestone {id}: {Milestone title}

From the roadmap ({roadmap path} on origin/{base}):
{the milestone's step table, verbatim}

Explore how to build this milestone. Check the main specs and existing code first, surface open questions and tradeoffs, and recommend a scope for a change proposal. Don't implement anything yet.

Then ask the open decisions one at a time, starting with the one the others depend on. Just before the first one, say: "Once all the decisions are captured, the next step is /opsx:propose." End this message on that first decision.

After the last decision is answered, summarize every decision in one table and end with: "Next step: run /opsx:propose to draft this into a proposal." Don't create the change or write its artifacts from explore mode, and don't ask whether to; /opsx:propose does that.
```

No dialog is involved, so create them all after the user confirms the picks. Write each prompt to a file first to avoid shell quoting problems:

```bash
conductor workspace create --name "m{id}-{short-name}" --branch "$BASE" --agent claude \
  --message-file .context/explore-{id}.md --json
```

Inside a workspace, `create` defaults to this workspace's project. Keep each result's deep link (`conductor workspace get <id> --json` also has it as `deepLink`).

## 5. Report

List each workspace created (ID, name, what it was told to explore) with its deep link, so the user can click straight into it.
