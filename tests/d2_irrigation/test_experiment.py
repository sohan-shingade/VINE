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
