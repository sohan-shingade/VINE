"""Error-correction challenger (D2): OLS core, causality, NaN policy."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.ecm import ecm_walk_forward, fit_ecm_ols, run_ecm_experiment


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")


def _cointegrated_pair(n: int = 2000, seed: int = 1) -> dict[str, pd.Series]:
    """Two probes sharing a slow walk, plus a mean-reverting spread on probe a."""
    rng = np.random.default_rng(seed)
    walk = np.cumsum(rng.normal(0, 0.05, n))
    ou = np.zeros(n)
    for t in range(1, n):
        ou[t] = 0.8 * ou[t - 1] + rng.normal(0, 0.4)
    idx = _idx(n)
    return {
        "a": pd.Series(25.0 + walk + ou, index=idx),
        "b": pd.Series(25.0 + walk, index=idx),
    }


def test_fit_ecm_ols_recovers_known_coefficients():
    rng = np.random.default_rng(0)
    spread = rng.normal(0, 1, 4000)
    delta = 0.3 - 0.5 * spread + rng.normal(0, 0.01, 4000)
    alpha, beta = fit_ecm_ols(spread, delta)
    assert abs(alpha - 0.3) < 0.01
    assert abs(beta + 0.5) < 0.01


def test_ecm_finds_reversion_and_beats_persistence_on_cointegrated_probes():
    h = 6
    levels = _cointegrated_pair()
    pred, diags = ecm_walk_forward(levels, "a", h, n_folds=3)
    assert diags
    # divergence above the cross-section predicts a fall back toward it
    assert all(d["beta"] < 0 for d in diags)
    assert all(d["spread_ar1"] < 1 for d in diags)
    y = levels["a"]
    pers = y.shift(h)
    ok = pred.notna() & y.notna() & pers.notna()
    mae_ecm = (y[ok] - pred[ok]).abs().mean()
    mae_pers = (y[ok] - pers[ok]).abs().mean()
    assert mae_ecm < 0.95 * mae_pers


def test_ecm_reduces_to_persistence_when_the_spread_carries_no_signal():
    n, h = 400, 6
    base = pd.Series(25.0 + np.sin(np.arange(n) * 2 * np.pi / h), index=_idx(n))
    levels = {"a": base, "b": base.copy()}  # identical probes: spread is exactly 0
    pred, diags = ecm_walk_forward(levels, "a", h, n_folds=2)
    assert diags
    assert all(d["beta"] == 0.0 for d in diags)
    pers = base.shift(h)
    ok = pred.notna()
    assert ok.any()
    np.testing.assert_allclose(pred[ok].to_numpy(), pers[ok].to_numpy())


def test_ecm_excludes_rows_where_any_probe_is_nan():
    h = 6
    levels = _cointegrated_pair(n=800, seed=2)
    clean_pred, _ = ecm_walk_forward(levels, "a", h, n_folds=2)
    # blank the OTHER probe at a last-fold decision time, past every training window
    t_star = 700
    holed = {"a": levels["a"].copy(), "b": levels["b"].copy()}
    holed["b"].iloc[t_star] = np.nan
    holed_pred, _ = ecm_walk_forward(holed, "a", h, n_folds=2)
    assert np.isfinite(clean_pred.iloc[t_star + h])
    assert np.isnan(holed_pred.iloc[t_star + h])  # never imputed
    others = np.ones(len(clean_pred), dtype=bool)
    others[t_star + h] = False
    np.testing.assert_array_equal(holed_pred.to_numpy()[others], clean_pred.to_numpy()[others])


def test_ecm_standardization_constants_come_from_the_training_fold_only():
    h = 6
    levels = _cointegrated_pair(n=600, seed=3)
    n = len(levels["a"])
    purged_stop = n // 2 - h + 1  # training stop after the h-1 label purge
    _, clean_diags = ecm_walk_forward(levels, "a", h, n_folds=1)
    shifted = {name: series.copy() for name, series in levels.items()}
    for series in shifted.values():
        series.iloc[purged_stop:] += 100.0
    _, shifted_diags = ecm_walk_forward(shifted, "a", h, n_folds=1)
    assert clean_diags and shifted_diags
    for key in ("alpha", "beta", "spread_ar1", "n_fit"):
        assert clean_diags[0][key] == shifted_diags[0][key]


def test_ecm_poison_tail_causality_h6():
    """Values after the first test row's decision time must not change its
    forecast (same poison-tail pattern as the ARIMA and Prophet tests)."""
    h = 6
    levels = _cointegrated_pair(n=600, seed=4)
    n = len(levels["a"])
    min_train = n // 2
    clean_pred, _ = ecm_walk_forward(levels, "a", h, n_folds=1)
    poisoned = {name: series.copy() for name, series in levels.items()}
    for series in poisoned.values():
        series.iloc[min_train - h + 1 :] += 1000.0  # everything past row 0's anchor
    poisoned_pred, _ = ecm_walk_forward(poisoned, "a", h, n_folds=1)
    assert np.isfinite(clean_pred.iloc[min_train])
    assert poisoned_pred.iloc[min_train] == clean_pred.iloc[min_train]


def test_run_ecm_experiment_schema_and_zero_self_skill():
    levels = _cointegrated_pair(n=700, seed=5)
    frames = {
        name: pd.DataFrame({"soil_water": series}, index=series.index)
        for name, series in levels.items()
    }
    cfg = IrrigationConfig(model="ecm", horizons_h=[6, 24], n_folds=3)
    results, diagnostics = run_ecm_experiment(frames, cfg)
    assert list(results.columns) == [
        "device",
        "model",
        "horizon_h",
        "n",
        "mae",
        "rmse",
        "precision",
        "recall",
        "skill_fold_median",
        "skill_fold_min",
        "skill_vs_persistence",
    ]
    for device in ("a", "b"):
        for h in (6, 24):
            block = results[(results.device == device) & (results.horizon_h == h)]
            assert set(block.model) == {"ecm", "persistence"}
    pers = results[results.model == "persistence"]
    assert np.allclose(pers.skill_vs_persistence, 0.0)
    assert np.allclose(pers.skill_fold_median, 0.0)
    assert np.allclose(pers.skill_fold_min, 0.0)
    assert len(diagnostics)
    assert diagnostics.spread_ar1.notna().all()
