#!/usr/bin/env python3
"""Check that powerups is current and that everything babysitter needs is in place. Read-only.

  doctor.py            print a table: ✓ fine, ⚠ worth knowing, ⛔ needs a fix (with the fix)

Local (CONDUCTOR_IS_LOCAL=1): also checks Conductor's database and the outbox table babysitter writes to.
Cloud: also checks the conductor CLI's token and which cloud workspaces were created before the latest release.
"""
import datetime, glob, json, os, re, sqlite3, subprocess, sys

REPO = "aaroncohn/openspec-conductor-powerups"
PLUGIN = "powerups@openspec-conductor-powerups"
OUTBOX = ["message_id", "session_id", "delivery_payload", "config", "mode", "asset_ids", "queue_order", "state",
          "send_attempt_count", "next_send_attempt_at", "created_at", "updated_at"]  # what conductor-local.py send writes
QUEUES = ("Babysitter HQ", "Open Actions", "Open Decisions", "Open Tests")
rows = []


def add(mark, what, detail="", fix=""):
    rows.append((mark, what, detail, fix))


def out(args, cwd=None, timeout=30):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def short(sha):
    return (sha or "")[:12]


def plugin_versions():
    # Installed copies of the plugin: user scope, and project scope for this repo.
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(config, "plugins/installed_plugins.json")) as f:
            installs = json.load(f).get("plugins", {}).get(PLUGIN, [])
    except (OSError, ValueError):
        installs = []
    return [(i.get("scope", "?"), short(i.get("gitCommitSha") or i.get("version")), i.get("lastUpdated", "")[:16],
             i.get("projectPath", "")) for i in installs]


def running_version():
    # This script runs from the plugin cache: .../powerups/<sha>/skills/doctor/doctor.py; or from a checkout.
    m = re.search(r"/powerups/([0-9a-f]{12,40})/skills/doctor/doctor\.py$", os.path.realpath(__file__))
    return short(m.group(1)) if m else "a checkout (--plugin-dir)"


def latest_release():
    sha = out(["git", "ls-remote", f"https://github.com/{REPO}.git", "HEAD"]).split()
    date = out(["gh", "api", f"repos/{REPO}/commits/{sha[0]}", "--jq", ".commit.committer.date"]) if sha else ""
    return short(sha[0]) if sha else "", date


def check_plugin(local):
    latest, latest_date = latest_release()
    running, installed = running_version(), plugin_versions()
    if not latest:
        add("⚠", "latest powerups release", "couldn't reach GitHub", "check the network; skipping version checks")
    if not installed:
        add("⛔", "powerups installed", "not in installed_plugins.json",
            "claude plugin marketplace add %s && claude plugin install %s" % (REPO, PLUGIN) + (" --scope project" if not local else ""))
    for scope, sha, updated, project in installed:
        where = f"{scope} scope" + (f" ({os.path.basename(project)})" if project else "")
        if latest and sha and not latest.startswith(sha) and not sha.startswith(latest):
            add("⛔", f"powerups {where}", f"{sha}, latest is {latest}",
                f"claude plugin marketplace update openspec-conductor-powerups && claude plugin update {PLUGIN}"
                + (f" --scope {scope}" if scope != "user" else ""))
        else:
            add("✓", f"powerups {where}", f"{sha}, updated {updated.replace('T', ' ')}")
    current = any(sha.startswith(running) or running.startswith(sha) for _, sha, _, _ in installed if sha)
    if running.startswith("a checkout"):
        add("⚠", "this session runs", running, "fine for working on the plugin; users run the installed one")
    elif installed and not current:
        add("⛔", "this session runs", f"{running}, older than what's installed", "start a new session in this workspace")
    else:
        add("✓", "this session runs", running)
    return latest_date


def check_tools(local):
    tools = [("gh", "PRs and CI"), ("openspec", "/opsx and change status"), ("python3", "the scripts")] + ([("sqlite3", "Conductor's database; ships with macOS")] if local else [])
    for tool, why in tools:
        found = bool(out(["which", tool]))
        add("✓" if found else "⛔", tool, "" if found else "not on PATH", "" if found else f"install it ({why})")
    logged = subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0
    add("✓" if logged else "⛔", "gh logged in", "" if logged else "no", "" if logged else "gh auth login (babysitter never does this for you)")
    spec = os.path.isdir("openspec")
    add("✓" if spec else "⚠", "openspec/ in this repo", "" if spec else "none", "" if spec else "run openspec init if this repo should use OpenSpec")


def check_repo_defaults():
    for f in ("AGENTS.md", "CLAUDE.md"):
        try:
            text = open(f).read()
        except OSError:
            continue
        m = re.search(r"^## babysitter\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if m:
            lines = [l.strip(" -") for l in m.group(1).strip().splitlines() if l.strip()]
            add("✓", f"## babysitter in {f}", "; ".join(lines)[:120])
            return
    add("⚠", "## babysitter section", "none in AGENTS.md or CLAUDE.md", "babysitter will ask for mode, digests and timezone on its first run and offer to save them")


def check_local():
    db = os.environ.get("CONDUCTOR_DB_PATH") or os.path.expanduser("~/Library/Application Support/com.conductor.app/conductor.db")
    if not os.path.exists(db):
        return add("⛔", "Conductor database", f"not at {db}", "set CONDUCTOR_DB_PATH; babysitter falls back to SendMessage without it")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cols = [r[1] for r in con.execute("pragma table_info(session_messages_outbox)")]
    except sqlite3.Error as e:
        return add("⛔", "Conductor database", str(e), "babysitter falls back to SendMessage; a Conductor update may have changed the database")
    missing = [c for c in OUTBOX if c not in cols]
    if not cols:
        add("⛔", "outbox table", "session_messages_outbox is gone", "a Conductor update changed the database: local messaging falls back to SendMessage; open an issue on the plugin")
    elif missing:
        add("⛔", "outbox table", f"missing columns: {', '.join(missing)}", "a Conductor update changed the database: local messaging falls back to SendMessage; open an issue on the plugin")
    else:
        add("✓", "Conductor database and outbox table", "columns match what babysitter writes")
    root = os.path.dirname(out(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]))
    names = [r[0] for r in con.execute(
        "select workspace_name from workspaces where repository_id = (select id from repos where root_path = ?) and state != 'archived'", (root,))]
    report_queues(names)


def check_cloud(latest_date):
    repo = os.path.basename(out(["git", "remote", "get-url", "origin"]).removesuffix(".git"))
    text = out(["conductor", "workspace", "list", "--mine", "--repo", repo, "--json", "--limit", "100"], timeout=60)
    if not text:
        return add("⛔", "conductor CLI", "no answer (auth?)", "turn on automatic API access in Conductor → Settings → General (new workspaces), or set CONDUCTOR_API_KEY")
    try:
        data = json.loads(text).get("data", [])
    except ValueError:
        return add("⛔", "conductor CLI", "output isn't JSON", "run: conductor workspace list --mine --json")
    add("✓", "conductor CLI", f"{len(data)} open workspaces of {repo}")
    report_queues([w.get("name", "") for w in data])
    if latest_date:
        stale = [w.get("name", "?") for w in data if (w.get("createdAt") or w.get("created_at") or "") < latest_date
                 and w.get("id") != os.environ.get("CONDUCTOR_WORKSPACE_ID")]
        if stale:
            add("⚠", "created before the latest powerups release", ", ".join(stale),
                "probably on an older version; in each: claude plugin marketplace add %s --scope project && claude plugin install %s --scope project, then a new session. Queue and change workspaces don't need it; only where you'll type /powerups: commands" % (REPO, PLUGIN))


def report_queues(names):
    hq = [n for n in names if n == "Babysitter HQ"]
    if len(hq) > 1:
        add("⛔", "Babysitter HQ", f"{len(hq)} open", "two babysitters would drive the same sessions: stop one (\"stop babysitting everything\") and archive it")
    elif hq:
        add("⚠", "Babysitter HQ", "one is open", "if it's from before an update, stop it and start a new one; its queues carry over")
    for q in QUEUES[1:]:
        n = names.count(q)
        add("✓" if n == 1 else "⚠" if n == 0 else "⛔", q, f"{n} open",
            "" if n == 1 else "babysitter creates it when it has an item" if n == 0 else "more than one: items will split across them; archive the empty one")


def main():
    local = os.environ.get("CONDUCTOR_IS_LOCAL", "1") != "0"
    latest_date = check_plugin(local)
    check_tools(local)
    check_repo_defaults()
    (check_local if local else lambda: check_cloud(latest_date))()
    print("| | check | found | fix |\n| --- | --- | --- | --- |")
    for mark, what, detail, fix in rows:
        print(f"| {mark} | {what} | {detail} | {fix} |")
    bad = sum(1 for r in rows if r[0] == "⛔")
    print(f"\n{bad} to fix" if bad else "\nAll good." + ("" if local else " (cloud)"))


if __name__ == "__main__":
    main()
