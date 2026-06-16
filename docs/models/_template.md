# Model card: <track>/<model>

> Copy this file to `docs/models/<track>/<model>.md` (or via `/model-card`).
> Fill every field from the actual run. Unknown → "TBD — pending run", never
> invent numbers.

## Model details
- **Track / deliverable:** e.g. irrigation (D2)
- **Architecture:** e.g. 2-layer LSTM encoder-decoder, multi-task head
- **Version / run:** MLflow run ID
- **Config:** path to the `configs/.../*.yaml` used
- **Author & date:**

## Intended use
- **Primary use:** e.g. forecast soil moisture at 6/12/24/48 h to advise irrigation.
- **Users:** vineyard operators via the VINE dashboard.
- **Out of scope:** decisions it must NOT be used for (e.g. overriding grower
  judgment on frost nights).

## Training data
- Source, blocks, date range, train/val split (walk-forward for time series).
- Features used; how gaps were handled.

## Evaluation
- **Metrics:** e.g. MAE/RMSE on moisture; precision/recall on irrigation trigger.
- **Baselines beaten:** naive persistence, threshold rule — by how much.
- **Protocol:** held-out period (e.g. train spring, validate summer).

## Limitations & caveats
- Where it fails (sensor types, blocks, weather regimes).
- Sparse-label / single-season caveats.

## Ethical & operational considerations
- Cost of false negatives (under-irrigation → crop stress) vs false positives
  (water waste). Human-in-the-loop expectation.
