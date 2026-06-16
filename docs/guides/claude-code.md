# Working with Claude Code

This repo is set up for [Claude Code](https://code.claude.com). The agent reads
`CLAUDE.md` at the start of every session; project-specific tooling lives in
`.claude/`.

## What's configured

| Thing | Where | Purpose |
|-------|-------|---------|
| Project memory | `CLAUDE.md` (+ `AGENTS.md` symlink) | Stack, commands, rules, gotchas — loaded every session |
| Personal notes | `CLAUDE.local.md` (gitignored) | Your own machine-specific notes |
| Permissions | `.claude/settings.json` | Pre-approves safe commands (make, uv, ruff, pytest…) |
| Auto-format hook | `.claude/hooks/ruff-format.sh` | Formats every Python file Claude edits (deterministic) |
| Slash commands | `.claude/commands/` | `/new-experiment`, `/devlog`, `/adr`, `/model-card` |
| Subagents | `.claude/agents/` | `geospatial-data`, `eval-reviewer`, `nrp-deploy` |

## Recommended workflow

1. **Plan mode** for anything non-trivial — let Claude read the relevant files
   and produce a plan before it edits.
2. Delegate domain work to the subagents (e.g. "use the geospatial-data agent to
   add zonal stats to vine.d1_pipeline.geo").
3. After training a model, run the `eval-reviewer` agent to independently check
   for leakage and honest baselines before you believe the numbers.
4. Use `/devlog` every two weeks to draft the GSoC blog post.
5. Keep `CLAUDE.md` lean — if Claude ignores a rule, the file is probably too
   long; prune it or convert the rule into a hook.

## House rules the agent follows

- Evidence before claims: run the check and show output.
- No model ships without beating baselines.
- Never commit data/model binaries (DVC handles those).
- Record decisions as ADRs, don't change tool choices silently.
