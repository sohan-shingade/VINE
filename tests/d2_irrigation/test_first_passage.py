"""Tests for D2 first-passage (barrier-crossing) probabilities."""

import math

import numpy as np
import pandas as pd

from vine.d2_irrigation.first_passage import (
    crossing_probability,
    ewma_drift_series,
    ewma_volatility_series,
    first_passage_probability,
    hourly_deltas,
)


def _hourly(values, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


# --- closed form ---------------------------------------------------------


def test_already_below_is_probability_one():
    assert crossing_probability(24.0, 25.0, 6, 0.0, 0.5) == 1.0
    assert crossing_probability(25.0, 25.0, 6, 0.0, 0.5) == 1.0  # at the barrier


def test_monotone_in_horizon():
    ps = [crossing_probability(27.0, 25.0, h, 0.0, 0.3) for h in (6, 12, 24, 48)]
    assert all(a <= b for a, b in zip(ps, ps[1:], strict=False))
    assert 0.0 < ps[0] < ps[-1] < 1.0


def test_monotone_in_distance_to_threshold():
    levels = [25.5, 26.0, 27.0, 30.0, 40.0]
    ps = [crossing_probability(lv, 25.0, 24, 0.0, 0.3) for lv in levels]
    assert all(a >= b for a, b in zip(ps, ps[1:], strict=False))


def test_sigma_to_zero_limits():
    # Above threshold, no drift: probability collapses to 0.
    assert crossing_probability(27.0, 25.0, 24, 0.0, 1e-12) < 1e-12
    assert crossing_probability(27.0, 25.0, 24, 0.0, 0.0) == 0.0
    # Drift carries the level below the threshold: probability collapses to 1.
    assert crossing_probability(27.0, 25.0, 24, -0.5, 1e-12) > 1 - 1e-12
    assert crossing_probability(27.0, 25.0, 24, -0.5, 0.0) == 1.0


def test_strong_drift_does_not_overflow():
    # Huge exp(2*mu*b/sigma^2) exponent; must stay finite and in [0, 1].
    p = crossing_probability(30.0, 25.0, 48, -1.0, 0.01)
    assert p == 1.0
    p = crossing_probability(80.0, 25.0, 6, -1.0, 0.01)
    assert 0.0 <= p <= 1.0 and math.isfinite(p)


def test_nan_inputs_give_nan():
    assert math.isnan(crossing_probability(float("nan"), 25.0, 6, 0.0, 0.3))
    assert math.isnan(crossing_probability(27.0, 25.0, 6, 0.0, float("nan")))


def test_matches_monte_carlo_random_walk():
    rng = np.random.default_rng(0)
    h, mu, sigma, level, thr = 48, -0.02, 0.4, 26.5, 25.0
    steps = rng.normal(mu, sigma, size=(20000, h))
    paths = level + np.cumsum(steps, axis=1)
    mc = float((paths.min(axis=1) <= thr).mean())
    p = crossing_probability(level, thr, h, mu, sigma)
    # The discrete walk misses intra-step dips, so the closed form sits a
    # touch above the Monte Carlo estimate.
    assert mc <= p <= mc + 0.06


# --- estimation ----------------------------------------------------------


def test_hourly_deltas_exclude_nan_gap_pairs():
    y = _hourly([10.0, 11.0, np.nan, 20.0, 21.0])
    d = hourly_deltas(y)
    # The jump across the NaN hour never appears as a delta.
    assert list(d.to_numpy()) == [1.0, 1.0]


def test_hourly_deltas_exclude_irregular_index_steps():
    idx = pd.to_datetime(
        ["2026-01-01 00:00", "2026-01-01 01:00", "2026-01-01 05:00", "2026-01-01 06:00"],
        utc=True,
    )
    y = pd.Series([10.0, 11.0, 30.0, 31.0], index=idx)
    d = hourly_deltas(y)
    # Only the two genuine one-hour pairs survive; the 4-hour jump is dropped.
    assert list(d.to_numpy()) == [1.0, 1.0]


def test_ewma_series_warmup_and_constant_case():
    y = _hourly(np.linspace(30, 20, 100))  # steady -10/99 per hour
    sig = ewma_volatility_series(y, halflife=24, min_pairs=24)
    mu = ewma_drift_series(y, halflife=24, min_pairs=24)
    # NaN until min_pairs deltas exist (delta 1 lands at row 1 -> row 24 has 24).
    assert sig.iloc[:24].isna().all() and not math.isnan(sig.iloc[24])
    assert math.isclose(sig.iloc[-1], 10 / 99, rel_tol=1e-9)  # constant slope: sigma == |delta|
    assert math.isclose(mu.iloc[-1], -10 / 99, rel_tol=1e-9)


def test_ewma_volatility_ignores_jump_across_gap():
    base = [10.0] * 40
    with_gap = base + [np.nan] + [30.0] * 40  # level shift hidden inside the gap
    sig = ewma_volatility_series(_hourly(with_gap), halflife=24, min_pairs=24)
    assert sig.iloc[-1] == 0.0  # all valid deltas are zero; the +20 jump is excluded


# --- causality -----------------------------------------------------------


def test_future_values_do_not_change_estimates_or_probability():
    rng = np.random.default_rng(1)
    y = _hourly(28 + np.cumsum(rng.normal(0, 0.2, 200)))
    t = y.index[120]
    poisoned = y.copy()
    poisoned.iloc[121:] = 0.0  # a crash after decision time

    for series_fn in (ewma_volatility_series, ewma_drift_series):
        clean = series_fn(y, halflife=24, min_pairs=24)
        dirty = series_fn(poisoned, halflife=24, min_pairs=24)
        assert clean.loc[t] == dirty.loc[t]

    p_clean = first_passage_probability(y.loc[:t], 24, 25.0, mu_mode="ewma")
    p_dirty = first_passage_probability(poisoned.loc[:t], 24, 25.0, mu_mode="ewma")
    assert p_clean == p_dirty


def test_first_passage_probability_modes_and_edge_cases():
    y = _hourly(np.linspace(30, 26, 100))
    p_zero = first_passage_probability(y, 48, 25.0, mu_mode="zero")
    p_ewma = first_passage_probability(y, 48, 25.0, mu_mode="ewma")
    # The drying drift pulls the level toward the barrier: higher probability.
    assert 0.0 <= p_zero < p_ewma <= 1.0

    assert math.isnan(first_passage_probability(_hourly([]), 6, 25.0))
    tail_nan = _hourly([30.0] * 50 + [np.nan])
    assert math.isnan(first_passage_probability(tail_nan, 6, 25.0))
    short = _hourly([30.0, 29.0, 28.0])
    assert math.isnan(first_passage_probability(short, 6, 25.0))  # too few pairs
