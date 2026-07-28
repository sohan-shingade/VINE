# Notebooks

Narrative, reproducible views over package APIs — **not** the source of truth.
Anything worth keeping graduates into `src/vine/` with tests; notebooks call
those APIs rather than duplicating pipeline or model logic. The two reviewed
entrypoints are:

- `01_irrigation_results.ipynb` — D2 persistence evidence and challenger benchmark.
- `02_pipeline_datasheet.ipynb` — D1 coverage, gaps, weather, geometry, and imagery profile.

After `dvc pull`, validate and execute both from the repository root with:

```bash
uv sync --extra notebooks --extra geo --extra sensors
uv run python scripts/check_notebooks.py --check-only
uv run python scripts/check_notebooks.py
```

Committed notebooks stay output-free; CI executes an in-memory copy and discards
outputs. Reproducible logic belongs in the package, not here.
