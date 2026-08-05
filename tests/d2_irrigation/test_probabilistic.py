"""Probabilistic CRPS challenger (D2): closed forms, causality, purge reuse."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.probabilistic import (
    RESULT_COLUMNS,
    SIGMA_FLOOR,
    climatology_sample,
    coverage,
    empirical_crps,
    ewma_sigma_series,
    fixed_sigma_series,
    gaussian_crps,
    pinball,
    run_probabilistic_experiment,
)


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")


def _random_walk(n: int = 3000, step: float = 0.2, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(30.0 + np.cumsum(rng.normal(0.0, step, n)), index=_idx(n))


# --- gaussian_crps closed form ---


def test_gaussian_crps_at_center_matches_hand_value():
    # mu = y: crps = sigma * (2/sqrt(2*pi) - 1/sqrt(pi))
    sigma = 2.0
    expected = sigma * (2.0 / math.sqrt(2.0 * math.pi) - 1.0 / math.sqrt(math.pi))
    got = gaussian_crps(np.array([5.0]), np.array([5.0]), np.array([sigma]))
    assert got.shape == (1,)
    assert abs(float(got[0]) - expected) < 1e-12


def test_gaussian_crps_hand_value_at_z_one():
    # z = 1, sigma = 1: Phi(1) = 0.841344746..., phi(1) = 0.241970724...
    got = float(gaussian_crps(np.array([1.0]), np.array([0.0]), np.array([1.0]))[0])
    assert abs(got - 0.6024413576276163) < 1e-9


def test_gaussian_crps_point_mass_reduction():
    y = np.array([1.0, 2.5, -3.0])
    mu = np.array([0.0, 2.5, 1.0])
    got = gaussian_crps(y, mu, np.zeros(3))
    np.testing.assert_allclose(got, np.abs(y - mu))


def test_gaussian_crps_large_z_approaches_abs_error():
    # As sigma -> 0 with the error fixed, crps -> |y - mu| (from below,
    # deficit sigma/sqrt(pi)).
    got = float(gaussian_crps(np.array([1.0]), np.array([0.0]), np.array([1e-4]))[0])
    assert got < 1.0
    assert abs(got - 1.0) < 1e-4


def test_gaussian_crps_scales_linearly_in_sigma_at_fixed_z():
    # crps(y, mu, sigma) = sigma * g(z), so doubling sigma and the error
    # doubles the score.
    one = float(gaussian_crps(np.array([1.0]), np.array([0.0]), np.array([1.0]))[0])
    two = float(gaussian_crps(np.array([2.0]), np.array([0.0]), np.array([2.0]))[0])
    assert abs(two - 2.0 * one) < 1e-12


def test_gaussian_crps_rejects_negative_sigma_and_propagates_nan():
    with pytest.raises(ValueError):
        gaussian_crps(np.array([1.0]), np.array([0.0]), np.array([-1.0]))
    got = gaussian_crps(np.array([1.0, 1.0]), np.array([0.0, 0.0]), np.array([np.nan, 1.0]))
    assert np.isnan(got[0]) and np.isfinite(got[1])


def test_honest_gaussian_spread_beats_point_mass_on_average():
    # Proper-scoring sanity: for y ~ N(mu, s^2), the true-sigma Gaussian has
    # lower expected CRPS than the point mass at mu (whose CRPS is |y - mu|).
    rng = np.random.default_rng(1)
    mu, s = 30.0, 1.5
    y = rng.normal(mu, s, 20000)
    crps_gauss = gaussian_crps(y, np.full_like(y, mu), np.full_like(y, s)).mean()
    crps_point = np.abs(y - mu).mean()
    assert crps_gauss < crps_point


# --- empirical_crps ---


def test_empirical_crps_single_member_is_abs_error():
    got = empirical_crps(np.array([3.0]), np.array([1.0, 3.0, 10.0]))
    np.testing.assert_allclose(got, [2.0, 0.0, 7.0])


def test_empirical_crps_two_member_hand_value():
    # sample {0, 2}, y = 1: integral of (F - H)^2 is 0.25 + 0.25 = 0.5
    got = float(empirical_crps(np.array([0.0, 2.0]), np.array([1.0]))[0])
    assert abs(got - 0.5) < 1e-12


def test_empirical_crps_rejects_empty_ensemble():
    with pytest.raises(ValueError):
        empirical_crps(np.array([]), np.array([1.0]))


# --- pinball and coverage ---


def test_pinball_median_is_half_abs_error():
    y = np.array([1.0, -2.0, 3.0])
    pred = np.array([0.0, 0.0, 0.0])
    assert abs(pinball(y, pred, 0.5) - 0.5 * np.abs(y).mean()) < 1e-12


def test_pinball_asymmetry_at_p90():
    # under-prediction costs q, over-prediction costs 1 - q
    assert abs(pinball(np.array([1.0]), np.array([0.0]), 0.9) - 0.9) < 1e-12
    assert abs(pinball(np.array([0.0]), np.array([1.0]), 0.9) - 0.1) < 1e-12


def test_coverage_counts_closed_interval():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    lo = np.array([0.0, 2.0, 1.0, 0.0])
    hi = np.array([1.0, 3.0, 2.0, 2.0])
    # inside: 0 in [0, 1] and 2 in [1, 2]; outside: 1 vs [2, 3] and 3 vs [0, 2]
    assert coverage(y, lo, hi) == 0.5


# --- sigma estimators ---


def test_ewma_sigma_series_value_and_warmup_alignment():
    h, min_pairs, c = 6, 24, 0.1
    n = 200
    y = pd.Series(np.arange(n) * c, index=_idx(n))  # constant h-step error c*h
    sig = ewma_sigma_series(y, h, halflife=72.0, min_pairs=min_pairs)
    # first error has target time h; warmup ends at h + min_pairs - 1; the
    # target-time alignment shifts by another h
    first = 2 * h + min_pairs - 1
    assert sig.iloc[:first].isna().all()
    expected = c * h * math.sqrt(math.pi / 2.0)
    np.testing.assert_allclose(sig.iloc[first:].to_numpy(), expected, rtol=1e-12)


def test_ewma_sigma_series_floor_on_constant_series():
    y = pd.Series(25.0, index=_idx(300))
    sig = ewma_sigma_series(y, 6)
    assert (sig.dropna() == SIGMA_FLOOR).all()


def test_ewma_sigma_poison_tail_causality():
    # Corrupting everything after the forecast origin t - h must change
    # neither the sigma nor the persistence forecast for target time t.
    h, t_star = 6, 250
    y = _random_walk(400, seed=2)
    clean = ewma_sigma_series(y, h)
    poisoned_y = y.copy()
    poisoned_y.iloc[t_star - h + 1 :] += 1000.0
    poisoned = ewma_sigma_series(poisoned_y, h)
    assert np.isfinite(clean.iloc[t_star])
    assert poisoned.iloc[t_star] == clean.iloc[t_star]
    assert poisoned_y.shift(h).iloc[t_star] == y.shift(h).iloc[t_star]


def test_fixed_sigma_uses_only_the_purged_training_region():
    # Same purge convention as every other rung: with one fold over rows
    # [0, n//2) purged by h - 1, corrupting rows from the purged stop onward
    # must leave the fold sigma unchanged.
    h, n = 6, 600
    y = _random_walk(n, seed=3)
    purged_stop = n // 2 - (h - 1)
    clean = fixed_sigma_series(y, h, n_folds=1)
    poisoned_y = y.copy()
    poisoned_y.iloc[purged_stop:] += 100.0
    poisoned = fixed_sigma_series(poisoned_y, h, n_folds=1)
    test_rows = clean.notna()
    assert test_rows.any()
    np.testing.assert_array_equal(poisoned[test_rows].to_numpy(), clean[test_rows].to_numpy())


def test_fixed_sigma_warmup_leaves_fold_nan():
    y = _random_walk(60, seed=4)
    sig = fixed_sigma_series(y, 6, n_folds=1, min_pairs=1000)
    assert sig.isna().all()


def test_climatology_sample_is_deterministic_capped_and_causal():
    y = _random_walk(500, seed=5)
    a = climatology_sample(y, 400, max_sample=100)
    b = climatology_sample(y, 400, max_sample=100)
    np.testing.assert_array_equal(a, b)
    assert len(a) == 100
    poisoned = y.copy()
    poisoned.iloc[400:] += 1000.0
    np.testing.assert_array_equal(climatology_sample(poisoned, 400, max_sample=100), a)
    small = climatology_sample(y, 50, max_sample=100)
    assert len(small) == 50


# --- the walk-forward runner ---


def test_run_experiment_schema_zero_self_skill_and_identical_rows():
    frames = {"a": pd.DataFrame({"soil_water": _random_walk(2000, seed=6)})}
    cfg = IrrigationConfig(model="probabilistic", horizons_h=[6, 24], n_folds=3)
    results = run_probabilistic_experiment(frames, cfg)
    assert list(results.columns) == RESULT_COLUMNS
    models = {
        "persistence-point",
        "gaussian-ewma",
        "gaussian-fixed",
        "climatology-ensemble",
    }
    for h in (6, 24):
        block = results[results.horizon_h == h]
        assert set(block.model) == models
        assert block.n.nunique() == 1  # every model scored on identical rows
    pers = results[results.model == "persistence-point"]
    assert np.allclose(pers.crps_skill, 0.0)
    assert np.allclose(pers.crps_skill_fold_median, 0.0)
    assert np.allclose(pers.crps_skill_fold_min, 0.0)
    # a point mass has a degenerate central interval: coverage ~ 0
    assert (pers.cov50 < 0.01).all()


def test_calibrated_gaussian_beats_point_mass_on_a_gaussian_walk():
    # On a true Gaussian random walk the h-step error is N(0, h * step^2), so
    # the EWMA-scaled Gaussian must show positive CRPS skill and coverage
    # near nominal.
    frames = {"a": pd.DataFrame({"soil_water": _random_walk(4000, step=0.3, seed=7)})}
    cfg = IrrigationConfig(model="probabilistic", horizons_h=[6], n_folds=3)
    results = run_probabilistic_experiment(frames, cfg)
    row = results[(results.model == "gaussian-ewma") & (results.horizon_h == 6)].iloc[0]
    assert row.crps_skill > 0.1
    assert row.crps_skill_fold_min > 0.0
    assert abs(row.cov50 - 0.50) < 0.07
    assert abs(row.cov90 - 0.90) < 0.05
    # the median quantile is the persistence level itself, so pinball at 0.5
    # equals half the persistence MAE for every persistence-centered model
    pers = results[(results.model == "persistence-point") & (results.horizon_h == 6)].iloc[0]
    assert abs(row.pinball_p50 - pers.pinball_p50) < 1e-12


def test_run_experiment_skips_gap_rows_never_imputes():
    y = _random_walk(2000, seed=8)
    y.iloc[1500:1520] = np.nan  # a holdout gap
    frames = {"a": pd.DataFrame({"soil_water": y})}
    cfg = IrrigationConfig(model="probabilistic", horizons_h=[6], n_folds=3)
    results = run_probabilistic_experiment(frames, cfg)
    full = run_probabilistic_experiment(
        {"a": pd.DataFrame({"soil_water": _random_walk(2000, seed=8)})}, cfg
    )
    # gap rows (and the h rows whose persistence anchor falls in the gap)
    # simply drop out of the shared scorable rowset
    assert results.n.iloc[0] < full.n.iloc[0]
