#!/usr/bin/env python3
"""Babysitter's state file, kept by a script so IDs, counts and the workspace table can't drift.

Works the same locally and in the cloud: it only touches .context/babysitter.json (or $BABYSITTER_STATE).

  state.py option set <key> <value>                  e.g. mode standard, digests "every 30 minutes", tz America/New_York
  state.py option get [<key>]
  state.py item add <OA|OD|OT> <title> [--grade release-blocking|normal|minor] [--workspace <name>]
                                                     prints the new ID (OA001, OD001, OT001, ...)
  state.py item set <ID> [--status open|answered|passed|failed|done|skipped] [--note <text>]
  state.py item list [OA|OD|OT] [--open]
  state.py item seed <OA|OD|OT> <n>                  continue numbering after n (an older queue's items)
  state.py workspace set <name> [--stage s] [--effort S|M|L|XL] [--progress p] [--next n] [--eta e]
                                [--monitoring yes|no] [--pr n] [--waiting w] [--gone]
  state.py sync-scan                                 stdin: conductor-local.py scan lines, or conductor
                                                     workspace list --json; marks workspaces present or gone
  state.py table                                     the digest's workspace table, markdown
  state.py counts                                    the digest's "Open actions: K (OA001, ...) · ..." line
  state.py show                                      everything, readable
  state.py digest-posted | last-digest               note a digest's time; print the last one
  state.py pause | resume | paused                   `/babysitter:pause` and `/babysitter:keep-going`; pause and resume print
                                                     the sessions to hold or release. No state file: error, not HQ.
  state.py other-hq                                  stdin: as sync-scan; exits non-zero if another Babysitter HQ is open
  state.py ignored                                   IDs of workspaces marked --monitoring no, for the watcher's --ignore
"""
import datetime, json, os, sys, tempfile

PATH = os.environ.get("BABYSITTER_STATE") or ".context/babysitter.json"
KINDS = {"OA": "actions", "OD": "decisions", "OT": "tests"}
GRADES = ("release-blocking", "normal", "minor")
QUEUES = ("Babysitter HQ", "Open Actions", "Open Decisions", "Open Tests")
COLUMNS = ("workspace", "stage", "effort", "progress", "next step", "ETA", "babysitter monitoring?")


def load():
    if not os.path.exists(PATH):
        return {"options": {}, "next": {k: 1 for k in KINDS}, "items": {}, "workspaces": {}, "digests": []}
    with open(PATH) as f:
        return json.load(f)


def save(state):
    os.makedirs(os.path.dirname(PATH) or ".", exist_ok=True)
    with open(PATH, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
        f.write("\n")


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="minutes")


def flags(args):
    # ["a", "--x", "1", "--gone"] -> (["a"], {"x": "1", "gone": True})
    pos, opts, i = [], {}, 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[key], i = args[i + 1], i + 2
            else:
                opts[key], i = True, i + 1
        else:
            pos.append(args[i]); i += 1
    return pos, opts


def item_add(state, kind, title, grade="normal", workspace=""):
    if kind not in KINDS:
        sys.exit(f"kind must be one of {', '.join(KINDS)}")
    if grade not in GRADES:
        sys.exit(f"grade must be one of {', '.join(GRADES)}")
    n = state["next"][kind]
    item_id = f"{kind}{n:03d}"
    state["next"][kind] = n + 1
    state["items"][item_id] = {"kind": kind, "title": title, "grade": grade, "workspace": workspace,
                               "status": "open", "created": now(), "note": ""}
    return item_id


def item_seed(state, kind, n):
    state["next"][kind] = max(state["next"][kind], int(n) + 1)


def open_items(state, kind=None):
    order = {g: i for i, g in enumerate(GRADES)}
    items = [(i, it) for i, it in state["items"].items() if it["status"] == "open" and (not kind or it["kind"] == kind)]
    return sorted(items, key=lambda x: (order[x[1]["grade"]], x[0]))


def counts(state):
    parts = []
    for kind, word in KINDS.items():
        ids = [i for i, _ in open_items(state, kind)]
        parts.append(f"Open {word}: {len(ids)}" + (f" ({', '.join(ids)})" if ids else ""))
    return "**" + " · ".join(parts) + "**"


def workspace_set(state, name, **fields):
    w = state["workspaces"].setdefault(name, {"name": name, "present": True})
    for k, v in fields.items():
        if v is None:
            continue
        if k == "monitoring":
            v = v in (True, "yes", "x", "true", "1")
        if k == "gone":
            w["present"] = False; continue
        w[k] = v
    return w


def sync_scan(state, text, self_path=None, self_id=None):
    seen = set()
    for r in scan_rows(text):
        if is_self(r, self_path, self_id):
            continue
        name = row_name(r)
        pr = r.get("pr")
        fields = {"path": r.get("path"), "branch": r.get("branch"), "session": r.get("session") or r.get("id"),
                  "stage": r.get("stage"), "pr": pr and pr.get("number")}
        if name not in state["workspaces"]:
            carry_over_rename(state, name, fields)
        workspace_set(state, name, present=True, **fields)
        seen.add(name)
    for name, w in state["workspaces"].items():
        if name not in seen:
            w["present"] = False
    return sorted(seen)


def scan_rows(text):
    # Accepts conductor-local.py scan (one JSON object per line: name, path, branch, session, stage, pr)
    # or conductor workspace list --json ({"data": [{id, name, ...}]}, pretty-printed over many lines).
    text = text.strip()
    try:
        whole = json.loads(text)
        if isinstance(whole, dict) and "data" in whole:
            return whole["data"]
    except ValueError:
        pass
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def is_self(r, self_path, self_id):
    if r.get("path") and self_path and os.path.realpath(r["path"]) == os.path.realpath(self_path):
        return True
    return bool(r.get("id") and self_id and r["id"] == self_id)


def row_name(r):
    return r.get("name") or os.path.basename(r.get("path") or "") or r.get("id")


def carry_over_rename(state, name, fields):
    # A stage rename is the same workspace: keep its effort, ETA and monitoring under the new name.
    for old, w in state["workspaces"].items():
        if (fields["path"] and w.get("path") == fields["path"]) or (fields["session"] and w.get("session") == fields["session"]):
            state["workspaces"][name] = {**state["workspaces"].pop(old), "name": name}
            return


def other_hqs(text, self_path=None, self_id=None):
    return [f"{row_name(r)} ({r.get('deepLink') or r.get('path') or r.get('id')})" for r in scan_rows(text)
            if bare(row_name(r) or "") == "Babysitter HQ" and not is_self(r, self_path, self_id)]


def pause(state):
    # Returns the sessions to hold, or None if already paused. Queues keep taking the user's answers.
    if state.get("paused"):
        return None
    held = [{"name": w["name"], "session": w.get("session") or ""} for n, w in sorted(state["workspaces"].items())
            if w.get("present", True) and w.get("monitoring") and bare(n) not in QUEUES]
    state["paused"] = {"since": now(), "held": held}
    return held


def resume(state):
    # Returns what pause() stored, or None if not paused.
    return state.pop("paused", None)


def ignored(state):
    # Cloud rows keep the workspace ID in "session"; local rows, the session. Each watcher's --ignore takes its own.
    return [w["session"] for w in state["workspaces"].values()
            if w.get("present", True) and w.get("monitoring") is False and w.get("session")]


def table(state):
    rows = [w for n, w in sorted(state["workspaces"].items()) if w.get("present", True) and bare(n) not in QUEUES]
    lines = ["| " + " | ".join(COLUMNS) + " |", "| " + " | ".join("---" for _ in COLUMNS) + " |"]
    for w in rows:
        pr = f" (#{w['pr']})" if w.get("pr") else ""
        lines.append("| " + " | ".join([
            w["name"] + pr, w.get("stage") or "", w.get("effort") or "", w.get("progress") or "",
            w.get("next") or "", w.get("eta") or "", "x" if w.get("monitoring") else ""]) + " |")
    if not rows:
        lines.append("| (no other open workspaces) |" + " |" * (len(COLUMNS) - 1))
    return "\n".join(lines)


def bare(name):
    # "apply-m10-alerts" -> "m10-alerts"; queue names never get a prefix, but strip defensively
    for p in ("explore-", "propose-", "apply-", "archive-"):
        if name.startswith(p):
            return name[len(p):]
    return name


def show(state):
    out = ([f"PAUSED since {state['paused']['since']}: do nothing on your own until `/babysitter:keep-going`", ""] if state.get("paused") else []) + ["options: " + (", ".join(f"{k}={v}" for k, v in sorted(state["options"].items())) or "(none)"),
           "last digest: " + (state["digests"][-1] if state["digests"] else "(none)"), "", table(state), "", counts(state)]
    for item_id, it in open_items(state):
        out.append(f"- {item_id} · {it['title']} · {it['grade']}" + (f" · from {it['workspace']}" if it["workspace"] else ""))
    waiting = [w for w in state["workspaces"].values() if w.get("present", True) and w.get("waiting")]
    if waiting:
        out += [""] + [f"{w['name']} is waiting on: {w['waiting']}" for w in waiting]
    return "\n".join(out)


def check():
    global PATH
    keep, PATH = PATH, os.path.join(tempfile.mkdtemp(), "s.json")
    try:
        s = load()
        assert item_add(s, "OD", "first") == "OD001" and item_add(s, "OD", "second", "minor") == "OD002"
        assert item_add(s, "OA", "key", "release-blocking", "apply-m1") == "OA001"
        item_seed(s, "OT", 16)
        assert item_add(s, "OT", "phone") == "OT017"
        item_seed(s, "OT", 3)                                   # never goes backwards
        assert s["next"]["OT"] == 18
        assert [i for i, _ in open_items(s, "OD")] == ["OD001", "OD002"]
        s["items"]["OD001"]["status"] = "answered"
        assert counts(s) == "**Open actions: 1 (OA001) · Open decisions: 1 (OD002) · Open tests: 1 (OT017)**"
        s["items"]["OD002"]["grade"] = "release-blocking"
        item_add(s, "OD", "third")                             # normal, newer: sorts after release-blocking
        assert [i for i, _ in open_items(s, "OD")] == ["OD002", "OD003"]
        scan = '\n'.join(json.dumps(r) for r in [
            {"name": "apply-m1-a", "path": "/w/a", "stage": "apply", "pr": {"number": 7, "state": "OPEN"}, "session": "s1"},
            {"name": "Open Tests", "path": "/w/t", "stage": "explore", "pr": None},
            {"name": "Babysitter HQ", "path": "/w/hq", "stage": "explore", "pr": None},
            {"name": "explore-m2-b", "path": "/w/b", "stage": "explore", "pr": None}])
        assert sync_scan(s, scan, self_path="/w/hq") == ["Open Tests", "apply-m1-a", "explore-m2-b"]
        workspace_set(s, "apply-m1-a", effort="M", eta="~2 h, 4 pm EST", monitoring="yes", next="rebase and merge")
        t = table(s)
        assert t.splitlines()[0] == "| " + " | ".join(COLUMNS) + " |"
        assert "| apply-m1-a (#7) | apply | M |  | rebase and merge | ~2 h, 4 pm EST | x |" in t
        assert "| explore-m2-b | explore |  |  |  |  |  |" in t and "Open Tests" not in t and "HQ" not in t
        assert sync_scan(s, scan.replace('"name": "explore-m2-b"', '"name": "propose-m2-b"'), self_path="/w/hq")
        assert "explore-m2-b" not in table(s) and "propose-m2-b" in table(s)   # renamed: old row marked gone
        cloud = json.dumps({"data": [{"id": "ws1", "name": "apply-m3-c", "branch": "m3"}, {"id": "hq", "name": "HQ"}]})
        assert sync_scan(s, cloud, self_id="hq") == ["apply-m3-c"] and "apply-m1-a" not in table(s)
        pretty = json.dumps({"data": [{"id": "ws1", "name": "apply-m3-c"}], "hasMore": False}, indent=2)   # what the CLI prints
        assert sync_scan(s, pretty, self_id="hq") == ["apply-m3-c"] and scan_rows("") == []
        one = json.dumps({"name": "m9", "path": "/w/9", "stage": "propose", "session": "s9"})
        sync_scan(s, one); workspace_set(s, "m9", effort="L", monitoring="yes")
        sync_scan(s, one.replace('"m9"', '"apply-m9"'))         # a rename keeps the row's fields
        assert s["workspaces"]["apply-m9"]["effort"] == "L" and s["workspaces"]["apply-m9"]["monitoring"] and "m9" not in s["workspaces"]
        workspace_set(s, "Open Tests", monitoring="yes", present=True)
        assert pause(s) == [{"name": "apply-m9", "session": "s9"}]   # a queue isn't held
        assert pause(s) is None and "PAUSED" in show(s)
        assert resume(s)["held"][0]["name"] == "apply-m9" and resume(s) is None and "PAUSED" not in show(s)
        hq = '\n'.join(json.dumps(r) for r in [{"name": "Babysitter HQ", "path": "/w/hq"}, {"name": "apply-m1", "path": "/w/a"}])
        assert other_hqs(hq, self_path="/w/hq") == [] and other_hqs(hq, self_path="/w/a") == ["Babysitter HQ (/w/hq)"]
        assert other_hqs(json.dumps({"data": [{"id": "h", "name": "Babysitter HQ", "deepLink": "conductor://x"}]}, indent=2)) == ["Babysitter HQ (conductor://x)"]
        assert other_hqs(json.dumps({"data": [{"id": "h", "name": "Babysitter HQ"}]}), self_id="h") == []
        save(s); assert load()["next"] == s["next"]
        m = load()
        workspace_set(m, "m7", session="w7", monitoring="no", present=True); workspace_set(m, "m8", session="w8", monitoring="yes")
        workspace_set(m, "m9", session="w9", monitoring="no", gone=True); workspace_set(m, "m6", session="w6")
        assert ignored(m) == ["w7"]
    finally:
        PATH = keep


def main(argv):
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    pos, opts = flags(args)
    if cmd == "other-hq":
        found = other_hqs(sys.stdin.read(), self_path=".", self_id=os.environ.get("CONDUCTOR_WORKSPACE_ID"))
        return sys.exit(f"another Babysitter HQ is open for this repo: {', '.join(found)}") if found else None
    if cmd in ("pause", "resume", "paused") and not os.path.exists(PATH):
        sys.exit(f"no babysitter state here ({PATH}): this isn't Babysitter HQ. Nothing changed; run this in the Babysitter HQ workspace.")
    state = load()
    if cmd == "ignored":
        return print(",".join(ignored(state)))
    if cmd == "option" and pos[:1] == ["set"] and len(pos) == 3:
        state["options"][pos[1]] = pos[2]
    elif cmd == "option" and pos[:1] == ["get"]:
        return print(state["options"].get(pos[1], "") if len(pos) > 1 else json.dumps(state["options"], indent=1))
    elif cmd == "item" and pos[:1] == ["add"] and len(pos) == 3:
        print(item_add(state, pos[1], pos[2], opts.get("grade", "normal"), opts.get("workspace", "")))
    elif cmd == "item" and pos[:1] == ["set"] and len(pos) == 2:
        it = state["items"].get(pos[1]) or sys.exit(f"no item {pos[1]}")
        if "status" in opts:
            it["status"] = opts["status"]
        if "note" in opts:
            it["note"] = opts["note"]
    elif cmd == "item" and pos[:1] == ["list"]:
        kind = pos[1] if len(pos) > 1 else None
        items = open_items(state, kind) if "open" in opts else sorted(
            (i, it) for i, it in state["items"].items() if not kind or it["kind"] == kind)
        return print("\n".join(f"{i} · {it['status']} · {it['grade']} · {it['title']}"
                               + (f" · from {it['workspace']}" if it["workspace"] else "") for i, it in items))
    elif cmd == "item" and pos[:1] == ["seed"] and len(pos) == 3:
        item_seed(state, pos[1], pos[2])
    elif cmd == "workspace" and pos[:1] == ["set"] and len(pos) == 2:
        workspace_set(state, pos[1], **{k: opts[k] for k in opts if k in
                      ("stage", "effort", "progress", "next", "eta", "monitoring", "pr", "waiting", "gone", "path", "session")})
    elif cmd == "sync-scan":
        print("\n".join(sync_scan(state, sys.stdin.read(), self_path=".", self_id=os.environ.get("CONDUCTOR_WORKSPACE_ID"))))
    elif cmd == "table":
        return print(table(state))
    elif cmd == "counts":
        return print(counts(state))
    elif cmd == "show":
        return print(show(state))
    elif cmd == "pause":
        held = pause(state)
        if held is None:
            return print(f"already paused since {state['paused']['since']}")
        print(f"paused at {state['paused']['since']}; sessions to hold:")
        print("\n".join(f"{h['name']}\t{h['session']}" for h in held) or "(none)")
    elif cmd == "resume":
        was = resume(state)
        if was is None:
            return print("not paused")
        print(f"resumed; paused since {was['since']}; sessions to release:")
        print("\n".join(f"{h['name']}\t{h['session']}" for h in was["held"]) or "(none)")
    elif cmd == "paused":
        return print(f"paused since {state['paused']['since']}" if state.get("paused") else "running")
    elif cmd == "digest-posted":
        state["digests"].append(now())
    elif cmd == "last-digest":
        return print(state["digests"][-1] if state["digests"] else "")
    else:
        sys.exit(__doc__)
    save(state)


if __name__ == "__main__":
    check()
    main(sys.argv[1:])
