#!/usr/bin/env python3
"""Message local Conductor sessions so the message and the reply show in that workspace's chat.

Conductor has no supported way to do this locally (its CLI only reaches cloud workspaces), so this
queues the message in Conductor's own outbox table, the queue its app drains when you send a message
yourself. It relies on Conductor internals: a Conductor update can break it. The Conductor app must
be open. Back up first:  sqlite3 "$CONDUCTOR_DB_PATH" ".backup '<file>'"

  conductor-local.py session <worktree path>          print the workspace's chat session id
  conductor-local.py send <session id> <message file> queue the message, wait until it's delivered
  conductor-local.py watch <session id> ...           block until one of them finishes a turn
"""
import datetime, json, os, sqlite3, sys, time, uuid

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


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "session" and len(args) == 1:
        session(*args)
    elif cmd == "send" and len(args) == 2:
        send(*args)
    elif cmd == "watch" and args:
        watch(args)
    else:
        sys.exit(__doc__)
