#!/usr/bin/env python3
"""Babysitter's cloud watcher and re-scan, through the conductor CLI. See cloud.md sections 1 and 4.

  watch.py watch <repo> [--ignore <id>,<id>] [<sessionId> ...]
      block until there's something to act on, print why, exit. --ignore: workspace IDs whose activity
      shouldn't wake HQ (`state.py ignored`). A watched session's workspace is skipped by itself.
  watch.py scan <repo>
      for every open workspace of the repo: its sessions and their newest messages. Only reads what's new
      since the last scan (.context/babysitter-scan.json); a workspace with no new activity gets one line.
      A workspace whose user ran `/opsx:propose` (or ff, continue, apply) is marked in the state file, and so
      are clues that it may be proposing (state.signals); the scan ends with the ADOPT NOW and CHECK NOW lines
      for the ones HQ isn't driving yet (state.py adopt).
  watch.py check
      the self-test
"""
import json, os, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

SEEN = ".context/babysitter-scan.json"
SKIP = os.environ.get("CONDUCTOR_WORKSPACE_ID")
NEWEST = 4       # assistant messages to show per session
CUT = 1500       # characters per message


def cli(*args):
    # To a file, not a pipe: the CLI cuts piped output off at 128 KB, which is a page or two of messages.
    with tempfile.TemporaryFile("w+") as f:
        subprocess.run(["conductor", "--json", *args], stdout=f, stderr=subprocess.DEVNULL)
        f.seek(0)
        try:
            return json.load(f)
        except ValueError:
            return {}


def status(s):
    d = cli("session", "status", s)
    return d.get("status") or "", d.get("updatedAt") or "", d.get("workspaceId") or ""


def workspaces(repo):
    # {id: (name, lastActivityAt)}, every page. None if a page failed: that's not every workspace gone.
    found, offset = {}, 0
    while True:
        d = cli("workspace", "list", "--mine", "--repo", repo, "--limit", "100", "--offset", str(offset))
        if "data" not in d:
            return None
        found.update({w["id"]: (w["name"], w.get("lastActivityAt") or "") for w in d["data"] if w["id"] != SKIP})
        if not d.get("hasMore"):
            return found
        offset += len(d["data"]) or 100


def changes(before, after, ignore):
    out = [f"new workspace: {after[w][0]}" for w in after if w not in before]
    out += [f"workspace gone: {before[w][0]}" for w in before if w not in after]
    out += [f"activity in unwatched workspace: {after[w][0]}" for w in after
            if w in before and w not in ignore and after[w][1] != before[w][1]]
    return out


def watch(repo, sessions, ignore, tick=30, scan_every=10 * 60):
    # Exits, printing why, when a session finishes a turn or works 30 minutes with no update, or when the
    # scan finds a workspace that's new, gone, or active without a session being watched. `updatedAt` is noted
    # at the start, so a short turn between checks still counts and a session already idle doesn't fire.
    first = {s: status(s) for s in sessions}
    start = {s: first[s][1] for s in sessions}
    seen = {s: (start[s], time.time()) for s in sessions}
    ignore = set(ignore) | {first[s][2] for s in sessions}
    known, last_scan = workspaces(repo), time.time()
    while True:
        time.sleep(tick)
        for s in sessions:
            st, updated, _ = status(s)
            if st and st not in ("working", "queued") and updated != start[s]:
                return f"{s} finished a turn"
            if st != "working" or updated != seen[s][0]:
                seen[s] = (updated, time.time())
            elif time.time() - seen[s][1] > 30 * 60:
                return f"{s} has been working for 30 minutes with no update"
        if time.time() - last_scan >= scan_every:
            now, last_scan = workspaces(repo), time.time()
            if now is None:
                continue
            found = changes(known, now, ignore) if known is not None else []
            if found:
                return "\n".join(found)
            known = now


def messages(session, after):
    # New messages, oldest first. With no last message: only the end of the transcript, which can be long.
    if after:
        args, offset = ["--after", after], 0
    else:
        args, offset = [], 0
        while cli("session", "message", session, "--limit", "1", "--offset", str(offset + 500)).get("data"):
            offset += 500
    out = []
    while True:
        d = cli("session", "message", session, "--limit", "100", "--offset", str(offset), *args)
        if "data" not in d:
            return None
        out += d["data"]
        if not d.get("hasMore") or not d["data"]:
            return out
        offset += len(d["data"])


def said(m):
    # (who, text) for what a person would read in the chat; None for tool calls and the like.
    c = m.get("content") or {}
    if m.get("type") == "userMessage":
        return "user", c.get("message") or ""
    return state.said(c.get("rawPayload")) if m.get("type") == "agent" else None


def newest(msgs):
    # Every user message (they hold the `/opsx:` commands), and the last few assistant ones, in order.
    lines = [x for x in map(said, msgs) if x]
    keep = sum(1 for who, _ in lines if who == "assistant") - NEWEST
    out = []
    for who, text in lines:
        if who == "assistant":
            keep -= 1
            if keep >= 0:
                continue
        out.append(f"[{who}] {text[:CUT]}")
    return out


def scan(repo, seen):
    # Prints the scan and updates `seen` in place. A workspace it couldn't read keeps its old activity, so the
    # next scan tries it again. Returns {id: (name, typed /opsx:propose or later, clues)} for those with either.
    now, found = workspaces(repo), {}
    if now is None:
        sys.exit("couldn't list the workspaces; nothing is verified. Fix the CLI (see cloud.md), then scan again.")
    for w, (name, activity) in sorted(now.items(), key=lambda x: x[1][0]):
        old = seen.get(w) or {}
        if old.get("activity") == activity:
            print(f"== {name} ({w}): no activity since the last scan")
            continue
        print(f"== {name} ({w}): active {activity}")
        ok, last, tail = True, old.get("last") or {}, old.get("tail") or {}
        sessions = cli("workspace", "session", w, "--limit", "100").get("data")
        for s in sessions if sessions is not None else []:
            msgs = messages(s["id"], last.get(s["id"]))
            if msgs is None:
                ok = False
                print(f"session {s['id']}: couldn't read its messages")
                continue
            if msgs:
                last[s["id"]] = msgs[-1]["id"]
            lines = [x for x in map(said, msgs) if x]
            typed = any(who == "user" and state.proposed(text) for who, text in lines)
            # the last thing the session said before this scan, so an offer then and the user's answer now pair up
            clues = state.signals(([("assistant", tail[s["id"]])] if s["id"] in tail else []) + lines)
            said_last = [text for who, text in lines if who == "assistant"]
            if said_last:
                tail[s["id"]] = said_last[-1][-CUT:]
            if typed or clues:
                f = found.setdefault(w, [name, False, []])
                f[1], f[2] = f[1] or typed, f[2] + clues
            print(f"session {s['id']}: {status(s['id'])[0] or 'status unknown'}")
            print("\n".join(newest(msgs)) or "(nothing new said)")
        if sessions is None:
            ok = False
            print("couldn't list its sessions")
        if ok:
            seen[w] = {"activity": activity, "last": last, "tail": tail}
    for w in [w for w in seen if w not in now]:
        del seen[w]
    return found


def mark(found):
    # Into the state file (cloud rows keep the workspace ID as "session"), then the ADOPT NOW and CHECK NOW lines.
    s = state.load()
    for w, (name, typed, clues) in found.items():
        old = (s["workspaces"].get(name) or {}).get("check") or []
        state.workspace_set(s, name, session=w, present=True, proposed=typed or None,
                            check=(old + [c for c in clues if c not in old])[-5:])
    state.save(s)
    return state.adopt_lines(s)


def check():
    global cli, SKIP
    real, keep = cli, SKIP
    SKIP = "hq"
    a = {"id": "a", "name": "explore-a", "lastActivityAt": "1"}
    b = {"id": "b", "name": "explore-b", "lastActivityAt": "1"}
    w = {"id": "w", "name": "apply-w", "lastActivityAt": "1"}
    hq = {"id": "hq", "name": "Babysitter HQ", "lastActivityAt": "1"}
    pages, msg = [], {"s1": [{"id": "m1", "type": "userMessage", "content": {"message": "/opsx:propose"}},
                             {"id": "m2", "type": "agent", "content": {"rawPayload": {"type": "tool"}}},
                             {"id": "m3", "type": "agent", "content": {"rawPayload": {"type": "assistant", "message": {
                                 "content": [{"type": "text", "text": "planning is done"}]}}}}]}

    def fake(*args):
        if args[:2] == ("workspace", "list"):
            return pages.pop(0) if len(pages) > 1 else pages[0]
        if args[:2] == ("session", "status"):
            return {"status": "working", "updatedAt": "1", "workspaceId": "w"}
        if args[:2] == ("workspace", "session"):
            return {"data": [{"id": "s1"}]}
        if args[:2] == ("session", "message"):
            all_ = msg.get(args[2], [])
            after = args[args.index("--after") + 1] if "--after" in args else None
            all_ = all_[[m["id"] for m in all_].index(after) + 1:] if after else all_
            return {"data": all_[int(args[args.index("--offset") + 1]):], "hasMore": False}
        return {}
    cli = fake
    try:
        def fires(before, after, **kw):
            pages[:] = [{"data": before}, {"data": after}]
            return watch("r", [], kw.get("ignore", []), tick=0, scan_every=0)
        # activity, new and gone each wake it; ignored IDs and HQ itself don't
        assert fires([a, b, hq], [a, {**b, "lastActivityAt": "2"}, hq]) == "activity in unwatched workspace: explore-b"
        assert fires([a, hq], [a, b, {**hq, "lastActivityAt": "2"}]) == "new workspace: explore-b"
        assert fires([a, b], [a]) == "workspace gone: explore-b"
        assert changes({"b": ("n", "1")}, {"b": ("n", "2")}, {"b"}) == []
        assert changes({"b": ("n", "1")}, {}, {"b"}) == ["workspace gone: n"]     # gone still counts when ignored
        # a watched session's workspace is skipped by itself, and only its turn wakes it
        pages[:] = [{"data": [w, a]}, {"data": [{**w, "lastActivityAt": "2"}, {**a, "lastActivityAt": "2"}]}]
        assert watch("r", ["s1"], [], tick=0, scan_every=0) == "activity in unwatched workspace: explore-a"
        # a failed list isn't every workspace gone
        pages[:] = [{"data": [a]}, {}, {"data": [a]}, {"data": []}]
        assert watch("r", [], [], tick=0, scan_every=0) == "workspace gone: explore-a"
        pages[:] = [{"data": [a], "hasMore": True}, {"data": [b]}]
        assert set(workspaces("r")) == {"a", "b"}                                  # every page
        # the scan reads only what's new, and skips a workspace with no new activity
        assert newest(msg["s1"]) == ["[user] /opsx:propose", "[assistant] planning is done"]
        assert messages("s1", "m1")[0]["id"] == "m2" and messages("s1", "m3") == []
        many = [{"type": "agent", "content": {"rawPayload": {"type": "assistant", "message": {
            "content": [{"type": "text", "text": str(i)}]}}}} for i in range(NEWEST + 2)]
        assert newest(msg["s1"][:1] + many)[0] == "[user] /opsx:propose" and newest(many)[0] == "[assistant] 2"
        seen, stdout = {}, sys.stdout
        pages[:] = [{"data": [a]}]
        sys.stdout = open(os.devnull, "w")
        try:
            assert scan("r", seen) == {"a": ["explore-a", True, []]}              # it ran /opsx:propose
            assert seen == {"a": {"activity": "1", "last": {"s1": "m3"}, "tail": {"s1": "planning is done"}}}
            msg["s1"].append({"id": "m4", "type": "userMessage", "content": {"message": "/opsx:apply"}})
            assert scan("r", seen) == {}
            assert seen["a"]["last"]["s1"] == "m3"                                 # no activity: not read
            pages[:] = [{"data": [{**a, "lastActivityAt": "2"}]}]
            scan("r", seen)
            assert seen["a"]["last"] == {"s1": "m4"}
            # an offer in one scan and the user's "yes" in the next still pair up
            seen["a"]["tail"]["s1"] = "Want me to start `/opsx:propose`? Reply yes."
            msg["s1"].append({"id": "m5", "type": "userMessage", "content": {"message": "yes"}})
            pages[:] = [{"data": [{**a, "lastActivityAt": "3"}]}]
            assert scan("r", seen)["a"][2] == ['it offered to start `/opsx:propose` and the user replied: "yes"']
            pages[:] = [{"data": []}]
            scan("r", seen)
            assert seen == {}                                                      # a gone workspace drops out
            keep_path, state.PATH = state.PATH, os.path.join(tempfile.mkdtemp(), "s.json")
            try:
                assert "ADOPT NOW" in mark({"a": ["explore-a", True, []]})[0]         # never driven: adopt it
                assert "CHECK NOW" in mark({"b": ["explore-b", False, ["it said: x"]]})[1]
                s = state.load(); state.workspace_set(s, "explore-a", monitoring="yes"); state.save(s)
                s = state.load(); state.workspace_set(s, "explore-b", not_yet=True); state.save(s)
                assert mark({"a": ["explore-a", True, []]}) == []                     # driven, and checked
            finally:
                state.PATH = keep_path
        finally:
            sys.stdout.close()
            sys.stdout = stdout
    finally:
        cli, SKIP = real, keep


def main(argv):
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "check" and not args:
        return
    if cmd == "scan" and len(args) == 1:
        seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
        try:
            typed = scan(args[0], seen)
            print("\n".join(mark(typed)))
        finally:
            os.makedirs(os.path.dirname(SEEN), exist_ok=True)
            with open(SEEN, "w") as f:
                json.dump(seen, f)
        return
    if cmd == "watch" and args:
        ignore = []
        if "--ignore" in args:
            i = args.index("--ignore")
            ignore = [x for x in args[i + 1].split(",") if x]
            args = args[:i] + args[i + 2:]
        return print(watch(args[0], args[1:], ignore))
    sys.exit(__doc__)


if __name__ == "__main__":
    check()
    main(sys.argv[1:])
