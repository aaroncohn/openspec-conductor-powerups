# Example: a digest in Babysitter HQ

The shape every digest has (step 6). `state.py digest` prints it with sections 5 and 6 (`state.py counts` and `state.py table`) and the last line already filled in. The product here is made up.

---

**Two things landed since 3:00 pm.** Shared folders (#214) merged: people on a team can now put notes in one folder and everyone sees changes as they're made, instead of emailing copies around. Its archive PR is in. The magic-link sign-in workspace hit a snag: its e-mail provider test key had expired, so I asked the session to use the sandbox key the repo already documents, and it's back to testing. Babysitter is taking over **apply-m14-export** now to keep it moving forward (you ran `/opsx:propose` there at 3:20 pm); you can tell me to stop babysitting it at any time.

**Waiting on you**
- **Magic-link sign-in (apply-m12-magic-link):** whether links expire after 15 minutes or 24 hours. It changes the copy on three screens, so the session stopped with a ⚠️ BLOCKED line. Go there to answer; it recommends 15 minutes.

**Working on now**
- **Magic-link sign-in (#219):** running the e-mail suite again with the sandbox key, then a browser pass of the sign-in flow. Merged in about 2 hours, around 6:30 pm EST, once you've answered the expiry question.
- **Note export to PDF (m14, no PR yet):** the session is building the export; first PR in about 3 hours, around 7:30 pm EST.
- **Share links (#222):** its turn to merge; rebased and re-running the checks that could be affected. Merged in about 20 minutes, around 4:20 pm EST.
- **Note tags (#221):** tested and ready, first in line to merge after share links, since both touch the note header. Merged around 5 pm EST.
- Everything merged around 8 pm EST; release in tomorrow morning's window (you asked for once a day).

**Critical path:** magic-link: **your expiry answer** → e-mail suite (~30 min) → rebase and merge → archive PR → full CI on main (~25 min) → dev → release window tomorrow 9 am. Holding it up: the expiry answer.

**Open actions: 1 (OA004) · Open decisions: 3 (OD011, OD012, OD014) · Open tests: 2 (OT006, OT007)**
You answered OD010 (keep the folder icon blue); nothing to change.

| workspace | stage | effort | progress | next step | ETA | babysitter monitoring? |
| --- | --- | --- | --- | --- | --- | --- |
| apply-m12-magic-link (#219) | apply | M | tasks done, e-mail suite re-running | your expiry answer, then merge | ~2 h, 6:30 pm EST | x |
| apply-m14-export | apply | L | building the export | open PR | ~3 h, 7:30 pm EST | x |
| apply-m16-share-links (#222) | apply | S | merging (its turn) | rebase, re-check, merge | ~20 min, 4:20 pm EST | x |
| apply-m13-tags (#221) | apply | S | waiting to merge (#1 in line) | rebase and merge on its turn | ~30 min, 5 pm EST | x |
| archive-m11-shared-folders (#214) | archive | M | merged, archive PR merged | `/babysitter:safe-to-archive` | done | x |
| explore-m15-search | explore | XL | user exploring | `/opsx:propose` | on you | |

Next digest around 4:30 pm EST.

---

A quiet one, when nothing moved:

---

**Quiet half hour:** both sessions are still testing, nothing finished.

**Working on now**
- **Magic-link sign-in (#219):** e-mail suite, 10 minutes in. Merged around 6:30 pm EST.
- **Note export to PDF (m14):** building. First PR around 7:30 pm EST.

**Critical path:** unchanged; holding it up: the expiry answer in apply-m12-magic-link.

**Open actions: 1 (OA004) · Open decisions: 3 (OD011, OD012, OD014) · Open tests: 2 (OT006, OT007)**

| workspace | stage | effort | progress | next step | ETA | babysitter monitoring? |
| --- | --- | --- | --- | --- | --- | --- |
| apply-m12-magic-link (#219) | apply | M | e-mail suite re-running | your expiry answer, then merge | ~2 h, 6:30 pm EST | x |
| apply-m14-export | apply | L | building the export | open PR | ~3 h, 7:30 pm EST | x |
| archive-m11-shared-folders (#214) | archive | M | merged, archive PR merged | `/babysitter:safe-to-archive` | done | x |
| explore-m15-search | explore | XL | user exploring | `/opsx:propose` | on you | |

Next digest around 5 pm EST.
