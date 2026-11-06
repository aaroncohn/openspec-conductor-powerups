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
                                [--not-yet]          its CHECK NOW clues were read and it isn't proposing yet
  state.py sync-scan                                 stdin: conductor-local.py scan lines, or conductor
                                                     workspace list --json; marks workspaces present or gone
  state.py table                                     the digest's workspace table, markdown
  state.py counts                                    the digest's "Open actions: K (OA001, ...) · ..." line
  state.py digest                                    the whole digest to fill in: sections, counts, table, next time
  state.py adopt                                     workspaces that ran `/opsx:propose` (or are past it) that HQ isn't
                                                     driving yet: take each over before posting anything. Then CHECK NOW:
                                                     clues that one may be proposing, for HQ to read and decide
  state.py show                                      everything, readable
  state.py digest-posted | last-digest               note a digest's time; print the last one
  state.py pause | resume | paused                   `/babysitter:pause` and `/babysitter:keep-going`; pause and resume print
                                                     the sessions to hold or release. No state file: error, not HQ.
  state.py other-hq                                  stdin: as sync-scan; exits non-zero if another Babysitter HQ is open
  state.py ignored                                   IDs of workspaces marked --monitoring no, for the watcher's --ignore
  state.py merge ready <workspace> --pr <n>          stdin: the PR's files (gh pr diff <n> --name-only); joins the line
  state.py merge next                                free lock: gives it to the next in line (most overlap first, then
                                                     oldest) and prints who; otherwise prints nothing to do
  state.py merge release <workspace>                 merged, failed or passed over: frees the lock or leaves the line
  state.py merge prodded                             note that the lock's holder has had its one prod
  state.py merge show                                the holder, how long it's held the lock, and the line
"""
import datetime, json, os, re, sys, tempfile

PATH = os.environ.get("BABYSITTER_STATE") or ".context/babysitter.json"
KINDS = {"OA": "actions", "OD": "decisions", "OT": "tests"}
GRADES = ("release-blocking", "normal", "minor")
QUEUES = ("Babysitter HQ", "Open Actions", "Open Decisions", "Open Tests")
# A user message that starts planning or building (the command comes first, as when it's typed), from which
# point HQ takes the workspace over. A message that only mentions the command doesn't count.
PROPOSED = re.compile(r"\s*(<command-name>)?/opsx[:-](propose|ff|continue|apply)\b")
# Clues HQ reads before deciding: the session offers to start /opsx:propose (and the user answers), or names
# /opsx:apply, which is what it usually says once the proposal is done.
OFFER = re.compile(r"/opsx[:-]propose\b")
APPLY = re.compile(r"/opsx[:-]apply\b")
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
        if k == "not_yet":
            w["dismissed"] = (w.get("dismissed") or []) + (w.get("check") or []); continue
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
                  "stage": r.get("stage"), "pr": pr and pr.get("number"), "proposed": r.get("proposed"),
                  "check": r.get("check")}
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
    # Returns what pause() stored, or None if not paused. The pause doesn't count against the merge lock's holder.
    was = state.pop("paused", None)
    h = merge_state(state)["holder"]
    if was and h:
        h.update(since=now(), prodded=False)
    return was


def merge_state(state):
    return state.setdefault("merge", {"holder": None, "queue": []})


def merge_line(state):
    # The change the others overlap with goes first, so they rebase once, onto it. A tie stays oldest-ready first.
    q = merge_state(state)["queue"]
    overlap = lambda a: sum(1 for b in q if b is not a and set(a["files"]) & set(b["files"]))
    return sorted(q, key=lambda a: -overlap(a))


def merge_ready(state, name, pr, files):
    m = merge_state(state)
    if m["holder"] and bare(m["holder"]["name"]) == bare(name):
        return
    for e in m["queue"]:
        if bare(e["name"]) == bare(name):
            e.update(name=name, pr=pr, files=files)
            return
    m["queue"].append({"name": name, "pr": pr, "files": files, "ready": now()})


def merge_next(state):
    # Returns the new holder, or None if the lock is taken or nobody's waiting.
    m = merge_state(state)
    line = merge_line(state)
    if m["holder"] or not line:
        return None
    m["queue"].remove(line[0])
    m["holder"] = {**line[0], "since": now(), "prodded": False}
    return m["holder"]


def merge_release(state, name):
    m = merge_state(state)
    if m["holder"] and bare(m["holder"]["name"]) == bare(name):
        m["holder"] = None
    m["queue"] = [e for e in m["queue"] if bare(e["name"]) != bare(name)]


def merge_show(state):
    m = merge_state(state)
    h = m["holder"]
    out = []
    if h:
        held = (datetime.datetime.now().astimezone() - datetime.datetime.fromisoformat(h["since"])).total_seconds() // 60
        out.append(f"holder: {h['name']} #{h['pr']}, {held:.0f} min, prodded: {'yes' if h['prodded'] else 'no'}")
    for i, e in enumerate(merge_line(state), 1):
        out.append(f"#{i} in line: {e['name']} #{e['pr']}, ready since {e['ready']}")
    return "\n".join(out)


def merge_progress(state, name):
    m = merge_state(state)
    if m["holder"] and bare(m["holder"]["name"]) == bare(name):
        return "merging (its turn)"
    for i, e in enumerate(merge_line(state), 1):
        if bare(e["name"]) == bare(name):
            return f"waiting to merge (#{i} in line)"
    return None


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
            w["name"] + pr, w.get("stage") or "", w.get("effort") or "", merge_progress(state, w["name"]) or w.get("progress") or "",
            w.get("next") or "", w.get("eta") or "", "x" if w.get("monitoring") else ""]) + " |")
    if not rows:
        lines.append("| (no other open workspaces) |" + " |" * (len(COLUMNS) - 1))
    return "\n".join(lines)


def proposed(text):
    return bool(PROPOSED.match(text or ""))


def to_adopt(state):
    # Ran `/opsx:propose` or later, or its files say it's past exploring, and HQ has never driven it or been told
    # to stop (--monitoring no). Done work (archive) stays put. Taking it over sets --monitoring yes, which clears it.
    return [n for n, w in sorted(state["workspaces"].items())
            if w.get("present", True) and bare(n) not in QUEUES and w.get("monitoring") is None
            and w.get("stage") != "archive" and (w.get("stage") in ("propose", "apply") or w.get("proposed"))]


def said(m):
    # (who, text) from a Conductor message in the SDK's shape (the local database's content, the cloud's
    # rawPayload); None for tool calls, results and the like.
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except ValueError:
            return None
    if not isinstance(m, dict) or m.get("type") != "assistant":
        return None
    text = "\n".join(b.get("text", "") for b in (m.get("message") or {}).get("content", []) if b.get("type") == "text")
    return ("assistant", text) if text else None


def signals(lines):
    # lines: [(who, text)], oldest first. A user message right after an offer to start /opsx:propose, and any
    # session message naming /opsx:apply. HQ reads them and decides; a typed command is `proposed` instead.
    out, offer = [], False
    for who, text in lines:
        if who == "assistant":
            offer = bool(OFFER.search(text))
            m = APPLY.search(text)
            if m:
                line = (text[:m.start()].split("\n")[-1] + text[m.start():].split("\n")[0]).strip()
                out.append(f'it said: "{line[:140]}"')
        elif offer and not proposed(text) and not text.startswith("Via Babysitter"):
            out.append(f'it offered to start `/opsx:propose` and the user replied: "{" ".join(text.split())[:80]}"')
            offer = False
    return out[-3:]


def to_check(state):
    adopt = set(to_adopt(state))
    return [(n, [c for c in w.get("check") or [] if c not in (w.get("dismissed") or [])])
            for n, w in sorted(state["workspaces"].items())
            if w.get("present", True) and bare(n) not in QUEUES and w.get("monitoring") is None
            and w.get("stage") != "archive" and n not in adopt
            and any(c not in (w.get("dismissed") or []) for c in w.get("check") or [])]


def adopt_lines(state):
    names, check = to_adopt(state), to_check(state)
    return (["ADOPT NOW, before you post anything: " + ", ".join(names) + ". Brief each (hq step 3), add it to the "
             "watcher, `state.py workspace set <name> --monitoring yes`, and say so in the digest."] if names else []) + (
            ["CHECK NOW, before you post anything: " + " | ".join(f"{n}: {'; '.join(c)}" for n, c in check)
             + ". Read each one's newest messages. If the user accepted the proposal, or it has one (a `tasks.md`, or "
             "it says planning is done), take it over as on the ADOPT NOW line. If not, `state.py workspace set "
             "<name> --not-yet`."] if check else [])


def interval(state):
    # Minutes between digests, from the digests option ("every 15 minutes", "every hour"); None for "on change".
    d = str(state["options"].get("digests") or "every 30 minutes").lower()
    if "change" in d:
        return None
    n = re.search(r"\d+", d)
    return int(n.group()) * (60 if "hour" in d else 1) if n else 60 if "hour" in d else 30


def clock(t, tz):
    try:
        import zoneinfo
        t = t.astimezone(zoneinfo.ZoneInfo(tz)) if tz else t
    except (ImportError, KeyError, ValueError):
        pass
    return t.strftime("%I:%M %p %Z").lstrip("0").replace("AM", "am").replace("PM", "pm").replace(":00 ", " ")


def digest(state, at=None):
    # The full digest for HQ to fill in, so its shape never depends on what the model remembers.
    at = at or datetime.datetime.now().astimezone()
    tz, every = state["options"].get("tz"), interval(state)
    last = state["digests"][-1] if state["digests"] else None
    ago = last and int((at - datetime.datetime.fromisoformat(last)).total_seconds() // 60)
    head = (f"[digests: {state['options'].get('digests') or 'every 30 minutes'}. Last one "
            + (f"{ago} min ago" if last else "never") + ". Fill in every <...> below and post it as one message, "
            "keeping the headings, the counts line, the table and the last line as they are. Then `state.py digest-posted`.]")
    waiting = [f"- **{w['name']}:** {w['waiting']}" for n, w in sorted(state["workspaces"].items())
               if w.get("present", True) and w.get("waiting") and bare(n) not in QUEUES]
    nxt = (f"Next digest around {clock(at + datetime.timedelta(minutes=every), tz)}." if every
           else "Next digest when something moves (you asked for digests on change).")
    return "\n".join(adopt_lines(state) + [head, "",
        "<What happened: a short paragraph or two, biggest first, as what the product's users get. Each workspace "
        "you took over: \"Babysitter is taking over <name> now to keep it moving forward. You can tell me to stop "
        "babysitting it at any time.\" Nothing moved: one line, e.g. \"Quiet quarter hour: everything's still running.\">",
        "", "**Waiting on you**"] + (waiting or ["<one line per blocking item or ⚠️ STOPPED workspace, with the workspace "
        "to go to; drop this heading if there are none>"]) + ["",
        "**Working on now**",
        "- <a bullet per workspace you're babysitting that isn't done, most important first: the feature in words "
        "(PR or roadmap number), what it's doing, what's next, when it should merge>",
        "- <one line: when everything should be merged, and when it should release>", "",
        "**Critical path:** <the chain to the next release, each link with what it waits on, the holding link in "
        "bold> Holding it up: <that link>.", "", counts(state), "<one line on any answer that came back, if one did>",
        "", table(state), "", nxt])


def bare(name):
    # "apply-m10-alerts" -> "m10-alerts"; queue names never get a prefix, but strip defensively
    for p in ("explore-", "propose-", "apply-", "archive-"):
        if name.startswith(p):
            return name[len(p):]
    return name


def show(state):
    every = interval(state)
    out = adopt_lines(state) + [f"digests: {f'every {every} min' if every else 'on change'}, the full shape from "
           "`state.py digest` every time, never skipped because nothing is building"] + ([f"PAUSED since {state['paused']['since']}: do nothing on your own until `/babysitter:keep-going`", ""] if state.get("paused") else []) + ["options: " + (", ".join(f"{k}={v}" for k, v in sorted(state["options"].items())) or "(none)"),
           "last digest: " + (state["digests"][-1] if state["digests"] else "(none)"), "", table(state), "", counts(state)]
    if merge_show(state):
        out += ["", "merge lock:", merge_show(state)]
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
        assert merge_next(m) is None and merge_show(m) == ""                    # nobody's waiting
        merge_ready(m, "apply-a", "1", ["x.py"])
        merge_ready(m, "apply-b", "2", ["y.py", "z.py"])
        merge_ready(m, "apply-c", "3", ["y.py"])
        merge_ready(m, "apply-a", "1", ["x.py"])                                # saying it twice doesn't move it
        assert [e["name"] for e in merge_line(m)] == ["apply-b", "apply-c", "apply-a"]  # overlap first, then oldest
        assert merge_next(m)["name"] == "apply-b" and merge_next(m) is None     # one at a time
        merge_ready(m, "apply-b", "2", ["y.py"])                                # the holder doesn't rejoin the line
        assert merge_progress(m, "apply-b") == "merging (its turn)" and merge_progress(m, "apply-c") == "waiting to merge (#2 in line)"
        workspace_set(m, "apply-c", progress="tests pass", present=True)
        assert "| waiting to merge (#2 in line) |" in table(m) and "tests pass" not in table(m)
        assert "holder: apply-b #2, 0 min, prodded: no" in show(m) and "#1 in line: apply-a #1" in show(m)
        m["merge"]["holder"].update(since="2000-01-01T00:00+00:00", prodded=True)
        assert ", prodded: yes" in merge_show(m) and ", 0 min" not in merge_show(m)
        pause(m); resume(m)                                                      # a pause doesn't use up the 45 minutes
        assert ", 0 min, prodded: no" in merge_show(m)
        merge_release(m, "apply-b")
        assert merge_next(m)["name"] == "apply-a"
        merge_release(m, "apply-c")                                              # one in line can drop out too
        assert merge_line(m) == [] and merge_progress(m, "apply-c") is None
        assert merge_progress(m, "archive-a") == "merging (its turn)"            # a rename is the same workspace
        workspace_set(m, "m7", session="w7", monitoring="no", present=True); workspace_set(m, "m8", session="w8", monitoring="yes")
        workspace_set(m, "m9", session="w9", monitoring="no", gone=True); workspace_set(m, "m6", session="w6")
        assert ignored(m) == ["w7"]
        # proposed workspaces get adopted: by command or by stage, until HQ drives them or is told to stop
        assert proposed("/opsx:propose") and proposed("<command-name>/opsx-apply</command-name>") and not proposed("/opsx:explore x") and not proposed("then I ran /opsx:propose")
        a = {"options": {}, "next": {k: 1 for k in KINDS}, "items": {}, "workspaces": {}, "digests": []}
        rows = [{"name": "explore-a", "path": "/w/a", "stage": "explore", "proposed": True},
                {"name": "propose-b", "path": "/w/b", "stage": "propose"}, {"name": "explore-c", "path": "/w/c", "stage": "explore"},
                {"name": "archive-d", "path": "/w/d", "stage": "archive", "proposed": True},
                {"name": "apply-e", "path": "/w/e", "stage": "apply"}, {"name": "Open Tests", "path": "/w/t", "stage": "apply"}]
        sync_scan(a, "\n".join(json.dumps(r) for r in rows))
        workspace_set(a, "apply-e", monitoring="no")
        assert to_adopt(a) == ["explore-a", "propose-b"] and "ADOPT NOW" in show(a) and "ADOPT NOW" in digest(a)
        workspace_set(a, "explore-a", monitoring="yes"); workspace_set(a, "propose-b", monitoring="yes")
        assert to_adopt(a) == [] and "ADOPT NOW" not in digest(a)
        # the digest always has every section, the counts, the table, and the next time on the user's interval
        a["options"].update(digests="every 15 minutes", tz="America/New_York")
        a["digests"] = ["2026-01-05T15:00-05:00"]
        d = digest(a, at=datetime.datetime.fromisoformat("2026-01-05T15:20-05:00"))
        assert "Last one 20 min ago" in d and d.endswith("Next digest around 3:35 pm EST.")
        for part in ("**Waiting on you**", "**Working on now**", "**Critical path:**", counts(a), table(a)):
            assert part in d, part
        assert interval({"options": {"digests": "every hour"}}) == 60 and interval({"options": {}}) == 30
        assert interval({"options": {"digests": "on change"}}) is None
        # clues: an offer to propose and the user's answer, and /opsx:apply named; HQ decides, --not-yet clears
        offer = [("assistant", "Next: run `/opsx:propose`, or reply yes and I'll start it."), ("user", "a")]
        assert signals(offer) == ['it offered to start `/opsx:propose` and the user replied: "a"']
        assert signals(offer[:1]) == [] and signals([offer[0], ("user", "Via Babysitter: go")]) == []
        assert signals([offer[0], ("user", "/opsx:propose")]) == []               # typed: that's `proposed`
        assert signals([("assistant", "Proposal done.\nThe next step is to run `/opsx:apply`.")]) == \
            ['it said: "The next step is to run `/opsx:apply`."']
        assert said('{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}') == ("assistant", "hi")
        assert said('{"type":"result"}') is None and said("not json") is None
        sync_scan(a, json.dumps({"name": "explore-f", "path": "/w/f", "stage": "explore", "check": signals(offer)}))
        assert [n for n, _ in to_check(a)] == ["explore-f"] and "CHECK NOW" in digest(a)
        workspace_set(a, "explore-f", not_yet=True)
        assert to_check(a) == [] and "CHECK NOW" not in digest(a)
        sync_scan(a, json.dumps({"name": "explore-f", "path": "/w/f", "stage": "explore", "check": signals(offer) + ["new"]}))
        assert to_check(a) == [("explore-f", ["new"])]                            # only a new clue comes back
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
    if cmd == "merge" and pos[:1] == ["show"]:
        return print(merge_show(state) or "free, nobody waiting")
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
                      ("stage", "effort", "progress", "next", "eta", "monitoring", "pr", "waiting", "gone", "path", "session")},
                      not_yet=opts.get("not-yet"))
    elif cmd == "merge" and pos[:1] == ["ready"] and len(pos) == 2 and "pr" in opts:
        merge_ready(state, pos[1], opts["pr"], [f for f in sys.stdin.read().split("\n") if f])
    elif cmd == "merge" and pos == ["next"]:
        h = merge_next(state)
        print(f"{h['name']}\t#{h['pr']}" if h else "nothing to do: the lock is taken or nobody's waiting")
    elif cmd == "merge" and pos[:1] == ["release"] and len(pos) == 2:
        merge_release(state, pos[1])
    elif cmd == "merge" and pos == ["prodded"]:
        if merge_state(state)["holder"]:
            merge_state(state)["holder"]["prodded"] = True
    elif cmd == "sync-scan":
        print("\n".join(sync_scan(state, sys.stdin.read(), self_path=".", self_id=os.environ.get("CONDUCTOR_WORKSPACE_ID"))
                         + adopt_lines(state)))
    elif cmd == "table":
        return print(table(state))
    elif cmd == "counts":
        return print(counts(state))
    elif cmd == "digest":
        return print(digest(state))
    elif cmd == "adopt":
        return print("\n".join(adopt_lines(state)) or "nothing to adopt or check")
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
