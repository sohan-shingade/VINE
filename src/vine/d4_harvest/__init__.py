"""D4 — harvest-timing forecasting: per-block harvest-readiness & days-to-harvest.

Harvest happens ~once per block per year, so labels are sparse; multi-year
history is critical. Tabular XGBoost baseline + sequential LSTM over the
season's daily feature vector. May be scoped to exploratory analysis if data
is insufficient (see proposal challenges).
"""
