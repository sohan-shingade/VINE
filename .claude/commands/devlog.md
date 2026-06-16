---
description: Draft a bi-weekly GSoC devlog/blog post from recent work
argument-hint: <phase or topic>   e.g. "D2 irrigation baselines"
---
Write a GSoC devlog post for: **$ARGUMENTS**

Read recent `git log`, the current `docs/roadmap.md`, and any new ADRs to ground
it in what actually happened. Then write `docs/devlog/YYYY-MM-DD-<slug>.md` with:

- **What I built** — concrete, with the deliverable (D1–D6) it advances.
- **Results** — numbers vs baselines if any model was trained (no numbers =
  say so honestly).
- **Decisions** — link any ADRs created.
- **Blockers / open questions for mentor.**
- **Next two weeks.**

Tone: honest engineering log, not marketing. Run the `humanizer` skill on the
draft before finishing. Add the post to the devlog index in `mkdocs.yml` nav.
