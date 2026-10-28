---
name: better-decision
description: Stop before a decision that matters, research it, and lay out at least four real options side by side, each with pros, cons, how hard it is to undo, and a 1–10 rating, then recommend one and wait for the user to pick. When there's an OpenSpec change in progress, record the pick in it. Run with /better-decision, optionally followed by what to decide (e.g. /better-decision how we cache sessions).
disable-model-invocation: true
---

# better-decision

Use this when a choice is about to get made by habit or by accident: two directions have come up and nobody has picked one, the current approach keeps fighting back, or the choice will be hard to change later. Stop, look at what's actually there, and compare real options before writing any code.

The output is a decision the user makes with what they need in front of them. Every option has to be one you'd defend. A straw man put there to make the favorite look good wastes the user's time.

## 1. Pin down the decision

From the conversation, plus anything typed after `/better-decision`, work out:

- **The decision**, as one concrete fork ("store drafts in Postgres or in the browser"), not a broad area ("storage").
- **What a good answer has to do:** two to four criteria from what's already been said (speed, cost, a deadline, a constraint the user named, a rule in the repo). These are what the ratings measure against.
- **What's off the table:** constraints already set, and approaches already tried or rejected, with the reason.

If the fork is unclear, ask one short question before going further. Don't guess and then present eight options for the wrong decision.

## 2. Research

Ground every option in the project before you write it:

- **The code:** how the project handles similar problems now, and the libraries and patterns it already uses.
- **The project's rules and past decisions:** `AGENTS.md`/`CLAUDE.md`, and docs such as a PRD, roadmap or decision log. In an OpenSpec repo, also the main specs in `openspec/specs/` and any change in progress in `openspec/changes/` (its proposal, design and open questions).
- **The conversation:** what's been tried, what failed, and what the user cares about.
- **Outside facts** when they matter (current limits, pricing, how a library behaves now). Check them instead of going from memory.

Keep the notes to yourself. They exist to make the options concrete; don't paste them at the user.

If the research shows that a rule the project already settled answers the question, say so and stop: name the rule and where it's written. Raise the alternatives only if the user wants to reopen it.

## 3. Write the options

Write **at least four**, spread across the real range of choices. Don't write four versions of the same idea. Include:

- the obvious default, written as an option, not taken for granted
- the current approach, if it's worth defending
- at least one bold option and at least one cautious one

If honest research turns up only three real options, show three and say why there isn't a fourth. That beats inventing one.

For each option:

```
### <letter>. <name>
<one or two sentences: what you'd actually do>

**Pros:** <two or three, each specific to this project>
**Cons:** <two or three, each specific to this project>
**Undo:** <easy / some work / hard>: <what switching away later would take>
**Rating: X/10**: <one or two sentences, against the criteria from step 1>
```

Pros and cons have to be specific. "Simpler" isn't a pro until it says what gets simpler. "Harder to maintain" isn't a con until it says what breaks, and for whom.

Ratings measure fit for this project, not general quality. If every option lands between 7 and 8, the range is too narrow: push one option further out.

**For a visual or front-end decision,** show the user a picture of each option (a quick mockup, a screenshot of a prototype, or the closest existing screen) and let them pick from the pictures. If you can't produce pictures here, say so.

## 4. Present and wait

Put the skimmable part first:

```
**Decision:** <the one-sentence fork>
**What matters:** <the criteria from step 1>

| | Option | Rating | Undo |
| --- | --- | --- | --- |
| a | <name> | 8/10 | easy |
| … | | | |

**My pick: <letter>. <name>.** <one or two sentences on why, given the criteria>
**What would change my mind:** <the fact or constraint that would make another option better>

---

<the full option blocks from step 3>

---

Reply with a letter, a letter plus changes, or your own idea.
```

Always recommend. A list without a pick hands the work back to the user.

Then **stop**. No plan, no code, no edits to files until the user answers.

## 5. After the user picks

- Confirm the pick in one line, along with any changes the user asked for.
- **Record it** wherever the project keeps decisions. In an OpenSpec repo with a change in progress, add it to that change's `design.md` under "Decisions": the decision, the pick, the options that lost and why, and anything that would reopen it. If there's no `design.md` yet, put it in `proposal.md`. If the project keeps a decision log (in `AGENTS.md`, `docs/`, or notes), add a line there too, dated, with who decided. Otherwise skip this step and say where the record would go.
- Then go back to what you were doing before, using the pick.

## Pitfalls

- **Skipping research:** options written without looking at the code are guesses.
- **Straw men:** an option you wouldn't defend doesn't count toward the four.
- **Hiding the pick:** the recommendation is required, and so is what would change it.
- **Starting early:** this skill ends with a question. Nothing gets built until the user answers.
- **Reopening settled decisions quietly:** if the project already decided this, say so first (step 2).
