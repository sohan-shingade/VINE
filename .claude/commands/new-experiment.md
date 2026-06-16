---
description: Scaffold a new, reproducible ML experiment (config + MLflow run)
argument-hint: <track> <name>   e.g. irrigation lstm-deeper
---
Create a new experiment for track **$1** named **$2**.

1. Copy the closest existing config in `configs/$1/` to `configs/$1/$2.yaml`;
   adjust hyperparameters for what we're testing. The config is the single
   source of truth — no hyperparameters in code.
2. Validate it loads against the track's pydantic config model
   (`vine.$1.config`).
3. State the hypothesis (what this run tests and the baseline it must beat) at
   the top of the YAML as a comment.
4. Show the exact command to run it: `uv run vine train $1 configs/$1/$2.yaml`.
5. Remind me to log params + metrics to MLflow and seed via `seed_everything()`.

Do NOT start training. Just scaffold and report the run command.
