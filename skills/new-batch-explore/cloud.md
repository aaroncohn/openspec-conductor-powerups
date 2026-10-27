# new-batch-explore in a Conductor cloud workspace

Read this when `CONDUCTOR_IS_LOCAL` is `0`. There's no Conductor database or `conductor://` link in a cloud sandbox; the `conductor` CLI (on the `PATH`) lists and creates workspaces instead. These sections replace steps 2, 4 and 5 of `SKILL.md`.

If `conductor` fails with an auth error, tell the user that the workspace has no API token: they can turn on automatic API access in Conductor → Settings → General (it applies to new workspaces) or set their own `CONDUCTOR_API_KEY`. Stop until it works.

## 2. Find what's already in flight

```bash
REPO=$(basename -s .git "$(git remote get-url origin)")
conductor workspace list --repo "$REPO" --json --limit 100    # page with --offset while hasMore
```

Archived workspaces aren't listed. Use each workspace's `name` to spot milestones already in flight, plus unarchived `openspec/changes/*` on `origin/$BASE` as in `SKILL.md`.

## 4. Create the workspaces

Name each workspace `{id}-{kebab-case milestone name}`, following the ID rules in `SKILL.md`. The CLI sets the name directly, so the prompt doesn't need the `Workspace/branch name:` line:

```
/opsx:explore Milestone {id}: {Milestone title}

From the roadmap ({roadmap path} on origin/{base}):
{the milestone's step table, verbatim}

Explore how to build this milestone. Check the main specs and existing code first, surface open questions and tradeoffs, and end with a recommended scope for a change proposal. Don't implement anything yet.
```

No dialog is involved, so create them all after the user confirms the picks. Write each prompt to a file first to avoid shell quoting problems:

```bash
conductor workspace create --name "{id}-{kebab-name}" --branch "$BASE" --agent claude \
  --message-file .context/explore-{id}.md --json
```

Inside a workspace, `create` defaults to this workspace's project. Keep each result's deep link (`conductor workspace get <id> --json` also has it as `deepLink`).

## 5. Report

List each workspace created (ID, name, what it was told to explore) with its deep link, so the user can click straight into it.
