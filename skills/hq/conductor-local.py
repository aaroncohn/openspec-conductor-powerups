#!/usr/bin/env python3
"""Message local Conductor sessions so the message and the reply show in that workspace's chat.

Conductor has no supported way to do this locally (its CLI only reaches cloud workspaces), so this
queues the message in Conductor's own outbox table, the queue its app drains when you send a message
yourself. It relies on Conductor internals: a Conductor update can break it. The Conductor app must
be open. Back up first:  sqlite3 "$CONDUCTOR_DB_PATH" ".backup '<file>'"

  conductor-local.py session <worktree path>          print the workspace's chat session id
  conductor-local.py send <session id> <message file> [--now]
                                                       deliver the message once the session is idle (--now: right away,
                                                       mid-turn), and wait up to 5 minutes for Conductor to deliver it
  conductor-local.py org                               the organization the app is switched to, and whether it's the
                                                       cloud one (the Create dialog follows it; see SKILL.md step 9)
  conductor-local.py watch [<session id> ...]         block until there's something to act on (see watch())
  conductor-local.py scan                              one JSON line per open workspace of this repo (read-only)
"""
import datetime, glob, json, os, sqlite3, subprocess, sys, time, uuid

DB = os.environ.get("CONDUCTOR_DB_PATH") or os.path.expanduser(
    "~/Library/Application Support/com.conductor.app/conductor.db")


def connect():
    return sqlite3.connect(DB, timeout=10)


def session(path):
    row = connect().execute(
        "select active_session_id from workspaces where workspace_path = ? and state != 'archived'",
        (os.path.realpath(path),)).fetchone()
    if not row or not row[0]:
        sys.exit(f"no active Conductor workspace at {path}")
    print(row[0])


def send(session_id, message_file, now_flag=False):
    # The row matches what the app writes in Conductor 0.92 (mode "steer", empty config, queue_order 1); the
    # older "queue" mode stopped being drained in 0.92. "steer" lands mid-turn, so unless --now was given,
    # wait for the session to go idle first, which is what the old "queue" did for us.
    message = open(message_file).read().strip()
    db = connect()
    if not db.execute("select 1 from sessions where id = ?", (session_id,)).fetchone():
        sys.exit(f"no session {session_id}; use SendMessage instead")
    if not now_flag:
        for _ in range(360):  # up to 30 minutes
            if not is_working(db, session_id):
                break
            time.sleep(5)
        else:
            sys.exit("session still working after 30 minutes; try again, or --now to steer it mid-turn")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    mid = str(uuid.uuid4())
    db.execute(
        "insert into session_messages_outbox (message_id, session_id, delivery_payload, config, mode, asset_ids,"
        " queue_order, state, send_attempt_count, next_send_attempt_at, created_at, updated_at)"
        " values (?, ?, ?, '{}', 'steer', '[]', 1, 'ready', 0, ?, ?, ?)",
        (mid, session_id, json.dumps({"message": message}), now, now, now))
    db.commit()
    for _ in range(150):  # usually seconds, sometimes close to 2 minutes
        time.sleep(2)
        if db.execute("select 1 from session_messages where id = ?", (mid,)).fetchone():
            print(f"delivered {mid}")
            return
    # Not picked up: take it back so it can't arrive later on top of a fallback message.
    db.execute("delete from session_messages_outbox where message_id = ?", (mid,))
    db.commit()
    sys.exit("not delivered within 5 minutes (is the Conductor app open?); message withdrawn")


def is_working(db, session_id):
    return (db.execute("select status from sessions where id = ?", (session_id,)).fetchone() or [""])[0] == "working"


def org():
    # The app's Create dialog (conductor://new) creates the workspace in the organization the switcher at the
    # top left is on, whatever path the link names. On a cloud organization that means a cloud workspace on
    # that organization's last repo. Say which it is before opening a dialog.
    path = os.path.join(os.path.dirname(DB), "local-storage.subsystem.active-organization.json")
    try:
        active = next(iter(json.load(open(path)).values())).strip('"')
    except (OSError, ValueError, StopIteration):
        return print("unknown: can't read the app's active organization")
    cloud = out(["conductor", "auth", "whoami", "--json"], ".")
    cloud_id = ""
    for line in cloud.splitlines():
        if line.startswith("Organization ID"):
            cloud_id = line.split()[-1]
    if cloud_id and active == cloud_id:
        print(f"cloud: the app is switched to your cloud organization ({active}); a Create dialog will make a cloud workspace")
    elif cloud_id:
        print(f"local: the app is switched to {active}, not the cloud organization")
    else:
        print(f"unknown: the app is switched to {active}; couldn't tell whether that's the cloud organization (conductor CLI not logged in)")


def watch(session_ids):
    # Exits, printing why, when one of these sessions finishes a turn or has been working for 30 minutes
    # without a new message, or when the scan (every 10 minutes) finds a workspace that's new, gone, or at
    # a new stage. Everything else stays quiet, so the coordinator only wakes when it has to act.
    db = connect()
    # Conductor records a "result" event at the end of every turn.
    turns = lambda s: db.execute(
        "select count(*) from session_messages where session_id = ? and role = 'assistant'"
        " and content like '{\"type\":\"result\"%'", (s,)).fetchone()[0]
    count = lambda s: db.execute("select count(*) from session_messages where session_id = ?", (s,)).fetchone()[0]
    working = lambda s: is_working(db, s)
    start = {s: turns(s) for s in session_ids}
    seen = {s: (count(s), time.time()) for s in session_ids}
    stages, last_scan = snapshot(), time.time()
    while True:
        time.sleep(5)
        for s in session_ids:
            if turns(s) > start[s]:
                return print(s, "finished a turn")
            n = count(s)
            if n != seen[s][0] or not working(s):
                seen[s] = (n, time.time())
            elif time.time() - seen[s][1] > 30 * 60:
                return print(s, "has been working for 30 minutes without a new message")
        if time.time() - last_scan > 10 * 60:
            now, last_scan = snapshot(), time.time()
            changes = scan_changes(stages, now)
            if changes:
                return print("\n".join(changes))


def snapshot():
    out(["git", "fetch", "origin", "-q"], ".")
    return {w["path"]: (w["name"] or os.path.basename(w["path"]), w["stage"]) for w in scan_rows()}


def scan_changes(before, after):
    changes = [f"new workspace: {after[p][0]} ({after[p][1]})" for p in after if p not in before]
    changes += [f"workspace gone: {before[p][0]}" for p in before if p not in after]
    changes += [f"stage changed: {after[p][0]} {before[p][1]} -> {after[p][1]}"
                for p in after if p in before and before[p][1] != after[p][1]]
    return changes


def check_scan_changes():
    a = {"/w/1": ("m1-a", "apply"), "/w/2": ("m2-b", "explore")}
    assert scan_changes(a, a) == []
    assert scan_changes(a, {**a, "/w/2": ("propose-m2-b", "explore")}) == []  # a rename alone isn't news
    assert scan_changes(a, {**a, "/w/2": ("m2-b", "propose")}) == ["stage changed: m2-b explore -> propose"]
    assert scan_changes(a, {"/w/1": a["/w/1"]}) == ["workspace gone: m2-b"]
    assert scan_changes({}, {"/w/3": ("m3", "explore")}) == ["new workspace: m3 (explore)"]


def stage(changes, code, merged):
    # changes: [(name, planning_complete)] not yet on the base branch; code: work outside openspec/ that
    # isn't on the base branch (an open PR or unmerged commits); merged: a PR of this branch is merged
    if changes:
        return "apply" if all(done for _, done in changes) else "propose"
    if code:
        return "apply"
    return "archive" if merged else "explore"


def check_stage():
    assert stage([], False, False) == "explore"
    assert stage([("a", False)], False, False) == "propose"
    assert stage([("a", True)], True, False) == "apply"
    assert stage([], True, False) == "apply"            # open PR without an OpenSpec change
    assert stage([], False, True) == "archive"          # merged, or its archive PR is open
    assert stage([("b", True)], False, True) == "apply"  # an older PR merged, a new change since
    assert stage([], True, True) == "apply"             # an older PR merged, new code since


def out(args, cwd):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def base_branch():
    ref = out(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], ".").strip()
    return os.environ.get("CONDUCTOR_DEFAULT_BRANCH") or ref.removeprefix("origin/") or "main"


def code_work(path, base, merged_pr):
    # Files outside openspec/ that this workspace changed (committed or not) and that differ from base.
    since = merged_pr and merged_pr["headRefOid"]
    if not (since and subprocess.run(["git", "merge-base", "--is-ancestor", since, "HEAD"], cwd=path,
                                     capture_output=True).returncode == 0):
        since = out(["git", "merge-base", base, "HEAD"], path).strip()
    if not since:
        return False
    files = [f for f in out(["git", "diff", "--name-only", since], path).split("\n")
             if f and not f.startswith("openspec/")]
    return bool(files and out(["git", "diff", "--name-only", base, "--", *files], path).strip())


def scan_rows():
    if not os.path.exists(DB):
        sys.exit(f"no Conductor database at {DB}; use the manual commands in SKILL.md step 1")
    root = out(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], ".").strip()
    root = os.path.dirname(root)  # the main checkout, which Conductor stores as the repo's root_path
    base = "origin/" + base_branch()
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = db.execute(
        "select w.workspace_name, w.workspace_path, w.branch, w.active_session_id, ifnull(s.status, '')"
        " from workspaces w left join sessions s on s.id = w.active_session_id"
        " where w.repository_id = (select id from repos where root_path = ?) and w.state != 'archived'",
        (root,)).fetchall()
    on_base = out(["git", "ls-tree", "--name-only", base + ":openspec/changes/"], ".").split()
    archived = {p.split("-", 3)[-1] for p in
                out(["git", "ls-tree", "--name-only", base + ":openspec/changes/archive/"], ".").split()}
    rows_out = []
    for name, path, branch, session_id, status in rows:
        changes, unarchived = [], []
        for d in sorted(glob.glob(os.path.join(path or "", "openspec/changes/*/"))):
            change = os.path.basename(d.rstrip("/"))
            if change == "archive" or change in archived:
                continue
            unarchived.append(change)
            if change in on_base:  # merged, waiting for its archive PR
                continue
            st = out(["openspec", "status", "--change", change, "--json"], path)
            done = json.loads(st).get("isPlanningComplete") if st else os.path.exists(os.path.join(d, "tasks.md"))
            changes.append((change, bool(done)))
        prs = json.loads(out(["gh", "pr", "list", "--head", branch, "--state", "all", "--json",
                              "number,state,headRefOid"], path) or "[]") if branch else []
        prs.sort(key=lambda p: (p["state"] == "OPEN", p["number"]), reverse=True)
        merged = [p for p in prs if p["state"] == "MERGED"]
        code = bool(path and os.path.isdir(path)) and code_work(path, base, merged[0] if merged else None)
        pr = prs[0] if prs else None
        rows_out.append({"name": name, "path": path, "branch": branch, "session": session_id,
                         "status": status, "base": base, "changes": unarchived,
                         "pr": pr and {"number": pr["number"], "state": pr["state"]},
                         "stage": stage(changes, code, bool(merged))})
    return rows_out


def scan():
    for w in scan_rows():
        print(json.dumps(w))


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "session" and len(args) == 1:
        session(*args)
    elif cmd == "send" and len(args) in (2, 3) and all(a == "--now" for a in args[2:]):
        send(args[0], args[1], now_flag=len(args) == 3)
    elif cmd == "org" and not args:
        org()
    elif cmd == "watch":
        check_scan_changes()
        watch(args)
    elif cmd == "scan" and not args:
        check_stage()
        scan()
    else:
        sys.exit(__doc__)
