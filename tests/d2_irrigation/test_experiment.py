"""Tests for the D2 experiment runner (synthetic data, deterministic)."""

import numpy as np
import pandas as pd
import pytest

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.experiment import run_experiment


def _daily_cycle_frame(n_hours: int = 24 * 30, seed: int = 0) -> pd.DataFrame:
    """Soil moisture with a strong daily cycle + slow drift + small noise."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-03-01", periods=n_hours, freq="1h", tz="UTC")
    hours = np.arange(n_hours)
    moisture = (
        30.0
        + 5.0 * np.sin(2 * np.pi * hours / 24)  # daily irrigation/ET cycle
        - 0.002 * hours  # slow dry-down
        + rng.normal(0, 0.2, n_hours)
    )
    return pd.DataFrame(
        {"soil_water": moisture, "soil_temperature": 20 + rng.normal(0, 1, n_hours)},
        index=idx,
    )


def test_results_table_shape_and_fair_n():
    cfg = IrrigationConfig(model="naive", horizons_h=[6, 24], n_folds=3)
    results = run_experiment(_daily_cycle_frame(), cfg)
    assert set(results["model"]) == {"persistence", "seasonal_naive", "climatology"}
    assert len(results) == 3 * 2  # models x horizons
    # fairness: every model scored on the same rows within a horizon
    for _, grp in results.groupby("horizon_h"):
        assert grp["n"].nunique() == 1
        assert (grp["n"] > 0).all()


def test_seasonal_naive_beats_persistence_on_daily_cycle():
    """On strongly daily-periodic data, 'same hour yesterday' must win at 6-12h."""
    cfg = IrrigationConfig(model="naive", horizons_h=[6, 12], n_folds=3)
    results = run_experiment(_daily_cycle_frame(), cfg).set_index(["model", "horizon_h"])
    for h in (6, 12):
        assert results.loc[("seasonal_naive", h), "mae"] < results.loc[("persistence", h), "mae"]
        assert results.loc[("seasonal_naive", h), "skill_vs_persistence"] > 0


def test_persistence_skill_is_zero_by_construction():
    cfg = IrrigationConfig(model="naive", horizons_h=[6], n_folds=3)
    results = run_experiment(_daily_cycle_frame(), cfg)
    persistence = results[results["model"] == "persistence"]
    assert (persistence["skill_vs_persistence"] == 0).all()


def test_ridge_runs_and_beats_persistence_on_learnable_series():
    cfg = IrrigationConfig(model="ridge", horizons_h=[6], n_folds=3)
    results = run_experiment(_daily_cycle_frame(), cfg).set_index(["model", "horizon_h"])
    assert results.loc[("ridge", 6), "skill_vs_persistence"] > 0


def test_gaps_are_masked_not_imputed():
    frame = _daily_cycle_frame()
    n_before = run_experiment(frame, IrrigationConfig(model="naive", horizons_h=[6], n_folds=3))[
        "n"
    ].iloc[0]
    frame.loc[frame.index[-100:-50], "soil_water"] = np.nan  # a 50h sensor outage
    n_after = run_experiment(frame, IrrigationConfig(model="naive", horizons_h=[6], n_folds=3))[
        "n"
    ].iloc[0]
    assert n_after < n_before  # gap rows dropped from scoring, for every model


def test_all_gap_holdout_raises():
    frame = _daily_cycle_frame(n_hours=200)
    frame.loc[frame.index[100:], "soil_water"] = np.nan
    with pytest.raises(ValueError, match="no scorable rows"):
        run_experiment(frame, IrrigationConfig(model="naive", horizons_h=[6], n_folds=3))


def _frame_with_weather(n_hours: int = 24 * 60, seed: int = 0) -> pd.DataFrame:
    """Daily-cycle moisture frame plus a `precip_mm` column (daily total,
    forward-filled hourly — the shape `add_lead_time_features` expects)."""
    frame = _daily_cycle_frame(n_hours, seed)
    rng = np.random.default_rng(seed + 1)
    n_days = n_hours // 24 + 1
    daily_precip = rng.uniform(0, 8, n_days)
    frame["precip_mm"] = np.repeat(daily_precip, 24)[:n_hours]
    return frame


def test_ridge_delta_with_forecast_features_e2e_no_leak_crash():
    """Smoke test: forecast_features + predict_delta run end to end across
    multiple horizons, producing a ridge_delta row and never crashing on the
    per-horizon mismatched `_next_*` column drop."""
    frame = _frame_with_weather()
    cfg = IrrigationConfig(
        model="ridge",
        horizons_h=[6, 24],
        n_folds=3,
        predict_delta=True,
        forecast_features=True,
    )
    results = run_experiment(frame, cfg)
    assert "ridge_delta" in set(results["model"])
    assert (results["n"] > 0).all()


def test_ridge_delta_beats_persistence_when_change_is_precip_driven():
    """Construct soil moisture whose CHANGE over h hours is exactly a linear
    function of the forward precip sum over that same window — the one thing
    `add_lead_time_features` exposes and persistence structurally cannot see.
    ridge_delta should recover it and clearly beat persistence."""
    n_hours = 24 * 60
    rng = np.random.default_rng(3)
    idx = pd.date_range("2026-01-01", periods=n_hours, freq="1h", tz="UTC")
    n_days = n_hours // 24
    daily_precip = rng.uniform(0, 8, n_days)
    precip_mm = np.repeat(daily_precip, 24)
    rate = precip_mm / 24.0
    effect = 0.8
    y = 30.0 + effect * np.cumsum(rate) + rng.normal(0, 0.001, n_hours)
    frame = pd.DataFrame(
        {
            "soil_water": y,
            "soil_temperature": 20 + rng.normal(0, 1, n_hours),
            "precip_mm": precip_mm,
        },
        index=idx,
    )
    cfg = IrrigationConfig(
        model="ridge", horizons_h=[6], n_folds=3, predict_delta=True, forecast_features=True
    )
    results = run_experiment(frame, cfg).set_index(["model", "horizon_h"])
    assert results.loc[("ridge_delta", 6), "skill_vs_persistence"] > 0


def test_arima_e2e_smoke():
    """Small AR(1) series, tiny order, few folds — just checking the harness
    wiring (walk_forward -> make_arima -> scored like every other model)."""
    n_hours = 24 * 10
    rng = np.random.default_rng(4)
    idx = pd.date_range("2026-01-01", periods=n_hours, freq="1h", tz="UTC")
    y = np.zeros(n_hours)
    for i in range(1, n_hours):
        y[i] = 0.9 * y[i - 1] + rng.normal(0, 0.1)
    frame = pd.DataFrame({"soil_water": y + 30.0}, index=idx)
    cfg = IrrigationConfig(model="arima", horizons_h=[1], n_folds=2, order=[1, 0, 0])
    results = run_experiment(frame, cfg)
    assert "arima" in set(results["model"])
    assert (results.loc[results["model"] == "arima", "n"] > 0).all()
