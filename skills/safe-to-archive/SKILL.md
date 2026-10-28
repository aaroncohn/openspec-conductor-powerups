---
name: safe-to-archive
description: Check whether the current Conductor workspace can be archived without losing work — uncommitted or unpushed changes, open or missing PRs, commits added after the merge, stashes, .context and other ignored files that exist only here, running processes, and (in OpenSpec repos) unarchived changes. Read-only; gives a yes/no verdict with the fix for each blocker. Use when the user runs /safe-to-archive or asks "can I archive this workspace/session?", "is this workspace done?", or "safe to archive?".
---

# safe-to-archive

Archiving a Conductor workspace deletes its worktree directory, including untracked and ignored files such as `.context/`. Pushed branches and PRs on GitHub survive. Decide whether anything would be lost or forgotten.

**Local or cloud.** Locally (`CONDUCTOR_IS_LOCAL=1`), the workspace is a git worktree: local branches live in the shared repository and survive archiving, so only this workspace's branch matters. In a cloud workspace (`CONDUCTOR_IS_LOCAL=0`), the sandbox is the only checkout and archiving deletes all of it, so every local branch matters (see step 1).

**Read-only.** Run the checks, report, then offer fixes. Do not commit, push, merge, or delete anything unless the user says so.

## 1. Gather facts

Run these from the workspace root (prefer one or two batched Bash calls):

```bash
git fetch origin -q
git branch --show-current
git status --porcelain                       # uncommitted + untracked
git rev-parse --abbrev-ref @{u} 2>/dev/null  # upstream, if any
git log --oneline @{u}..HEAD 2>/dev/null     # unpushed commits
gh pr view --json number,url,state,baseRefName,headRefOid,mergedAt 2>/dev/null
git stash list --format='%gd %gs' | grep -F "$(git branch --show-current)"
git status --ignored --porcelain | grep '^!!'   # ignored files, incl. .context/
ps -Ao pid,command | grep -F "$PWD" | grep -v grep
```

Target branch: the PR's `baseRefName` if there is a PR; otherwise the Conductor target from the system prompt; otherwise `origin/HEAD`. Then:

```bash
git log --oneline origin/<target>..HEAD      # commits on this branch not in target
```

If there is no PR, also check whether the branch's content already landed (e.g. merged by another route): `git diff --stat origin/<target> HEAD -- $(git diff --name-only $(git merge-base origin/<target> HEAD) HEAD)`. Empty means the content is already in the target.

**Cloud only:** check every local branch, not just this one: `git for-each-ref refs/heads --format='%(refname:short) %(upstream:short)'`. For each, look for unpushed commits (`git rev-list --count <upstream>..<branch>`, or no upstream at all) and whether its work landed in the target (`gh pr list --head <branch> --state all`, or an empty `git diff origin/<target> <branch>`). Also look for any cloud browser session still running for this workspace (for example, with Browserbase and `BROWSERBASE_API_KEY` set: `GET https://api.browserbase.com/v1/sessions?status=RUNNING` with header `X-BB-API-Key`). End it first so its saved logins are written back.

From the ignored files, skip regenerable ones (`node_modules`, build output, caches, `.playwright-mcp/`) and pick out anything that looks worth keeping: notes, scripts, plans, `.env` files with values that live nowhere else.

If the repo has an `openspec/` directory, also run `openspec list` (or `ls openspec/changes`, excluding `archive/`) and `git diff --name-only $(git merge-base origin/<target> HEAD) HEAD -- openspec/changes`.

## 2. Classify

**Blockers** (not safe — work would be lost or stranded):

| Check | Blocker when |
| --- | --- |
| Working tree | `git status --porcelain` shows anything outside gitignored paths |
| Unpushed | Commits exist that aren't on the remote branch |
| Other branches (cloud only) | Another local branch has unpushed commits, or no upstream and content that isn't in the target |
| PR | PR is `OPEN`, or there's no PR and the branch has commits whose content isn't in the target |
| After-merge commits | PR is `MERGED` but `HEAD` ≠ `headRefOid` and the extra commits' content isn't in the target |
| Stash | A stash entry was made on this branch |
| OpenSpec | A change in `openspec/changes/` (not `archive/`) was created or edited on this branch and not archived |

**Heads-ups** (safe, but say so):
- `.context/` or other ignored files that exist only here: list them; they'll be deleted. Call out any that look worth keeping (notes, plans, `.env` values that live nowhere else) and offer to copy them.
- Processes running from this directory (dev servers, watchers): they'll lose their directory. Give the PIDs. In the cloud, also any running cloud browser session (end it first so its logins are saved).
- PR is `CLOSED` without merging: the work was abandoned on purpose? Ask.
- Squash-merge leftovers: Conductor may still show a diff after a squash merge. That's fine if the content is in the target.
- Repo with a `dev` → `main` flow: if the merged work isn't in `origin/main` yet, note it isn't in production. Not a blocker — promotion can be done from any workspace. If the branch added database migrations, remind the user to apply them to production before promoting.

## 3. Report

Lead with the verdict on one line:

- `✅ Safe to archive.` followed by any heads-ups (max 5 bullets).
- `⛔ Not safe to archive yet.` followed by one numbered line per blocker: what, where, and the fix (e.g. "2 unpushed commits on `feature-x` → push and open a PR into `dev`").

End with one next step: either "Archive it in Conductor" or an offer to fix the first blocker ("Want me to commit and push these 3 files?").
