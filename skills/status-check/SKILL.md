---
name: status-check
description: Where things stand, from whichever workspace it's run in. In Babysitter HQ it's a full digest with the workspace table. In an Open Actions, Open Decisions or Open Tests workspace it's how many items are open, each by ID with a line on what it is. In any other workspace it's that workspace's stage, PR and checks, and what's left before merge. Use when the user runs /status-check or asks "where are we?", "what's open?", "status?".
---

# status-check

Say where things stand, in the shape that fits the workspace you're in. Work out which one from this chat first; if it isn't obvious, check in this order:

1. **Babysitter HQ:** `/babysitter` ran in this chat, or `.context/babysitter.json` exists here.
2. **A queue:** this chat's first message is the Open Actions, Open Decisions or Open Tests queue prompt ("You're the Open … queue for /babysitter").
3. **Anything else:** a change workspace.

Times are in the user's timezone, as in babysitter ("4:10 pm EST"), never UTC.

## In Babysitter HQ

Post a digest now, exactly as babysitter's step 6 describes it: what happened, waiting on you, working on now with estimates, the critical path, the open counts with their IDs, the workspace table from a fresh scan, and when the next scheduled digest is due. Don't shorten it because it was asked for: the table is the point. Doesn't reset the digest clock.

## In Open Actions, Open Decisions or Open Tests

From this chat's ledger (every item received, minus every "Done:", "Answered:" or "Result:" line), say how many are open, then list them by ID, one per line, in the order you'd present them (release-blocking, normal, minor; oldest first within each), with a few words on what each one is and the workspace it came from:

```
4 open decisions.
- OD005 · spam-check threshold (m2.2, apply-m2.2-spam-check) · release-blocking
- OD016 · name of the "replace photo" button (m3.1, apply-m3.1-profile-photo) · minor
…
Say "next" to pick up with OD005, or name an ID to jump to it.
```

Then stop; don't present an item until the user asks. If the ledger is unclear (a reply never got its "Done:"/"Answered:"/"Result:" line), say which IDs you're unsure about rather than guess.

## In any other workspace

One short block on this workspace: its OpenSpec stage (`openspec status --change <name>`, or "no change" if there isn't one), its branch and whether it's pushed, its PR and the state of its checks (`gh pr view --json state,mergeStateStatus,statusCheckRollup`), what's left before merge (tasks not done, a review, a rebase), and what it's waiting on, if anything. A table is overkill for one workspace; a few lines will do. If babysitter is driving this workspace ("Via Babysitter:" messages in this chat), say so and point to Babysitter HQ for the whole picture.
