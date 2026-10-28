#!/usr/bin/env python3
"""Message local Conductor sessions so the message and the reply show in that workspace's chat.

Conductor has no supported way to do this locally (its CLI only reaches cloud workspaces), so this
queues the message in Conductor's own outbox table, the queue its app drains when you send a message
yourself. It relies on Conductor internals: a Conductor update can break it. The Conductor app must
be open. Back up first:  sqlite3 "$CONDUCTOR_DB_PATH" ".backup '<file>'"

  conductor-local.py session <worktree path>          print the workspace's chat session id
  conductor-local.py send <session id> <message file> queue the message, wait until it's delivered
  conductor-local.py watch <session id> ...           block until one of them finishes a turn
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


def send(session_id, message_file):
    message = open(message_file).read().strip()
    db = connect()
    row = db.execute("select config from session_state where session_id = ?", (session_id,)).fetchone()
    if not row or not row[0]:
        sys.exit(f"session {session_id} has no saved config; use SendMessage instead")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    mid = str(uuid.uuid4())
    db.execute(
        "insert into session_messages_outbox (message_id, session_id, delivery_payload, config, mode, asset_ids,"
        " queue_order, state, send_attempt_count, next_send_attempt_at, created_at, updated_at)"
        " values (?, ?, ?, ?, 'queue', '[]', 0, 'ready', 0, ?, ?, ?)",
        (mid, session_id, json.dumps({"message": message}), row[0], now, now, now))
    db.commit()
    for _ in range(60):  # Conductor picked up test messages in 14-20s
        time.sleep(2)
        if db.execute("select 1 from session_messages where id = ?", (mid,)).fetchone():
            print(f"delivered {mid}")
            return
    # Not picked up: take it back so it can't arrive later on top of a fallback message.
    db.execute("delete from session_messages_outbox where message_id = ?", (mid,))
    db.commit()
    sys.exit("not delivered within 2 minutes (is the Conductor app open?); message withdrawn")


def watch(session_ids):
    # Conductor records a "result" event at the end of every turn; fire when a session gets a new one.
    db = connect()
    turns = lambda s: db.execute(
        "select count(*) from session_messages where session_id = ? and role = 'assistant'"
        " and content like '{\"type\":\"result\"%'", (s,)).fetchone()[0]
    start = {s: turns(s) for s in session_ids}
    while True:
        time.sleep(5)
        for s in session_ids:
            if turns(s) > start[s]:
                print(s, "finished a turn")
                return


def stage(changes, pr_state):
    # changes: [(name, planning_complete)]; pr_state: "OPEN", "MERGED", "CLOSED" or None
    if pr_state == "MERGED":
        return "archive"
    if not changes:
        return "explore"
    return "apply" if all(done for _, done in changes) else "propose"


def check_stage():
    assert stage([], None) == "explore"
    assert stage([("a", False)], None) == "propose"
    assert stage([("a", True)], "OPEN") == "apply"
    assert stage([("a", True)], "MERGED") == "archive"


def out(args, cwd):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def scan():
    if not os.path.exists(DB):
        sys.exit(f"no Conductor database at {DB}; use the manual commands in SKILL.md step 1")
    root = out(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], ".").strip()
    root = os.path.dirname(root)  # the main checkout, which Conductor stores as the repo's root_path
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = db.execute(
        "select w.workspace_name, w.workspace_path, w.branch, w.active_session_id, ifnull(s.status, '')"
        " from workspaces w left join sessions s on s.id = w.active_session_id"
        " where w.repository_id = (select id from repos where root_path = ?) and w.state != 'archived'",
        (root,)).fetchall()
    archived = {os.path.basename(p).split("-", 3)[-1] for p in
                out(["git", "ls-tree", "--name-only", "origin/main", "openspec/changes/archive/"], ".").split()}
    for name, path, branch, session_id, status in rows:
        changes = []
        for d in sorted(glob.glob(os.path.join(path or "", "openspec/changes/*/"))):
            change = os.path.basename(d.rstrip("/"))
            if change == "archive" or change in archived:
                continue
            st = out(["openspec", "status", "--change", change, "--json"], path)
            done = json.loads(st).get("isPlanningComplete") if st else os.path.exists(os.path.join(d, "tasks.md"))
            changes.append((change, bool(done)))
        prs = json.loads(out(["gh", "pr", "list", "--head", branch or "", "--state", "all", "--json",
                              "number,state"], path) or "[]") if branch else []
        pr = prs[0] if prs else None
        print(json.dumps({"name": name, "path": path, "branch": branch, "session": session_id,
                          "status": status, "changes": [c for c, _ in changes], "pr": pr,
                          "stage": stage(changes, pr and pr["state"])}))


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "session" and len(args) == 1:
        session(*args)
    elif cmd == "send" and len(args) == 2:
        send(*args)
    elif cmd == "watch" and args:
        watch(args)
    elif cmd == "scan" and not args:
        check_stage()
        scan()
    else:
        sys.exit(__doc__)
