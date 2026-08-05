# ADR-0010: Cost-loss economic value for D2 irrigation alert rules

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Sohan Shingade (+ mentor)

## Context
The D2 forecasting ladder ended with persistence plus a fixed threshold after
fifteen challenger families failed the ADR-0003 gate (worst-fold skill > 0).
The open question is now decision quality rather than forecast accuracy. An
alert that fires on nearly every hour can post an excellent hit rate and still
be worthless to a grower, and Brier or log loss cannot expose that. The
cost-loss model is standard in operational meteorology (Murphy 1977,
Richardson 2000) and is essentially absent from irrigation-ML papers, which
score MAE/RMSE on the moisture level.

## Decision
Evaluate irrigation alert rules by cost-loss economic value across a grid of
cost-to-loss ratios, alongside proper scores (Brier, log loss). A rule counts
as useful only where its economic value is positive for some plausible ratio
range.

Economic value is V = (E_climate - E_forecast) / (E_climate - E_perfect),
where E_climate is the cheaper of always irrigating and never irrigating, and
E_perfect pays the cost exactly on event hours. V = 1 is perfect; V <= 0 means
a trivial constant strategy beats the rule. The Bayes rule under this loss is
to act when the predicted crossing probability exceeds the cost-to-loss ratio,
so one probability forecast induces a whole family of rules, one per ratio.

## Considered options
- **Cost-loss economic value plus proper scores (chosen)**: measures what an
  alert is worth to the decision maker; exposes always-on rules that accuracy
  metrics reward.
- **Proper scores only (Brier, log loss)**: good for calibration, but blind to
  whether acting on the alerts would beat a constant strategy.
- **Hit rate / precision-recall only**: familiar, but an always-fire rule can
  look strong under high event prevalence; no cost model.

## Consequences
- **Good:** experiment runners for alert rules emit an economic-value table
  across cost ratios (implemented in `scripts/d2_stopping.py`); model cards
  for alert-style outputs report value curves, and a shipped threshold must
  show where on the ratio axis it is defensible.
- **Bad:** the true cost-to-loss ratio at Iron Horse is unknown, so results
  are reported over a ratio grid instead of a single point, which is one more
  table per experiment. Proper scores remain reported for calibration, so this
  adds a lens rather than replacing one.
