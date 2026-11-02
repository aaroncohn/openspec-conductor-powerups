# Example: the first message in a new explore workspace

What the explore prompt (step 4) should produce: findings, a recommended scope, then **one** decision, and stop. The product is made up.

---

Once all the decisions are captured, the next step is /opsx:propose.

## What I found

Milestone 14 adds "export a note to PDF". The notes spec already has a print view (`specs/notes/print.md`), and the web app renders it at `/notes/:id/print`. There's no PDF library in the repo. Two paths: render the print view in a headless browser on the server, or let the browser's own print-to-PDF do it from the print view.

## Recommended scope

One change, `note-export-pdf`: a "Download PDF" item in the note menu, server-side rendering of the existing print view, and a short expiry on the generated file. Out of scope: exporting a whole folder, and custom page sizes.

## Decision 1 of 3: where the PDF gets made

This one first, because the other two (file expiry, what the button says) depend on it.

- **a. On the server, from the print view** **(recommended):** same PDF for everyone, works on phones; adds a headless browser to the server image (~150 MB) and a few seconds per export.
- **b. In the browser, via print-to-PDF:** nothing new on the server; the result differs by browser, and on phones it's a poor experience.
- **c. A PDF library on the server:** small and fast; the print view's layout would have to be rebuilt in it, and kept in sync.

Which one?
