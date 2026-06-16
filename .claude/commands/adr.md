---
description: Create a new Architecture Decision Record (MADR format)
argument-hint: <decision title>
---
Create the next ADR for the decision: **$ARGUMENTS**

1. Find the highest-numbered file in `docs/adr/` and use the next number (NNNN).
2. Copy `docs/adr/0000-template.md` to `docs/adr/NNNN-<kebab-title>.md`.
3. Fill it in: Context (the forces at play), Decision (what we chose),
   Considered options (with pros/cons), Consequences (good and bad).
   Status starts `Proposed`.
4. If this supersedes an earlier ADR, mark the old one `Superseded by NNNN`.
5. Add it to the ADR list in `docs/adr/index.md` and the wiki nav.

Be specific and honest about trade-offs — an ADR with no downsides is wrong.
