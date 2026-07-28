"""Pooled cross-sensor forecaster (D2): alignment + causal walk-forward."""

from __future__ import annotations

import numpy as np
import pandas as pd

import vine.d2_irrigation.pooled as pooled
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.pooled import align_frames, run_pooled_experiment
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice


def _synth_frame(start: str, n: int, level: float, seed: int) -> pd.DataFrame:
    """A gently drifting soil-moisture-like series on an hourly grid."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    walk = level + np.cumsum(rng.normal(0, 0.2, n))
    return pd.DataFrame(
        {"soil_water": walk, "soil_temperature": 20 + rng.normal(0, 1, n)}, index=idx
    )


def test_align_frames_puts_all_on_one_grid():
    a = _synth_frame("2026-01-01", 100, 27.0, 1)
    b = _synth_frame("2026-01-01 03:00", 100, 18.0, 2)  # offset start
    aligned = align_frames({"a": a, "b": b})
    idx = next(iter(aligned.values())).index
    assert all(f.index.equals(idx) for f in aligned.values())  # shared grid
    assert idx.equals(a.index.union(b.index))


def test_pooled_runs_and_scores_each_device_vs_its_persistence():
    frames = {
        "s1": _synth_frame("2026-01-01", 400, 27.0, 1),
        "s2": _synth_frame("2026-01-01", 400, 18.0, 2),
    }
    cfg = IrrigationConfig(model="gbt", horizons_h=[6, 24], n_folds=3)
    res = run_pooled_experiment(frames, cfg)
    # every device (+ ALL) gets a pooled row and a persistence row per horizon
    for dev in ("s1", "s2", "ALL"):
        for h in (6, 24):
            block = res[(res.device == dev) & (res.horizon_h == h)]
            assert set(block.model) == {"pooled_gbt", "persistence"}
    # persistence scored against itself is exactly zero skill
    pers = res[res.model == "persistence"]
    assert np.allclose(pers.skill_vs_persistence, 0.0)


def test_pooled_fit_uses_exact_h_minus_one_purged_boundary(monkeypatch):
    n, horizon, n_folds = 120, 6, 3
    frames = {
        "s1": _synth_frame("2026-01-01", n, 27.0, 1),
        "s2": _synth_frame("2026-01-01", n, 18.0, 2),
    }
    cfg = IrrigationConfig(model="ridge", horizons_h=[horizon], n_folds=n_folds)
    train_lengths: list[int] = []

    def spy_fit_predict(cfg, X_train, y_train, X_tests):
        train_lengths.append(len(y_train))
        return {device: np.zeros(len(X_test)) for device, X_test in X_tests.items()}

    monkeypatch.setattr(pooled, "_fit_predict_pooled", spy_fit_predict)
    run_pooled_experiment(frames, cfg)

    splits = expanding_splits(n, n_folds=n_folds)
    expected = [
        len(frames) * (purged_train_slice(train, horizon - 1).stop or 0) for train, _ in splits
    ]
    assert train_lengths == expected


def test_pooled_earlier_fold_predictions_ignore_purged_boundary_labels(monkeypatch):
    n, horizon = 120, 6
    frames = {
        "s1": _synth_frame("2026-01-01", n, 27.0, 1),
        "s2": _synth_frame("2026-01-01", n, 18.0, 2),
    }
    cfg = IrrigationConfig(model="ridge", horizons_h=[horizon], n_folds=3)
    first_test = expanding_splits(n, n_folds=3)[0][1]
    boundary = range(first_test.start - horizon + 1, first_test.start)

    captured: list[np.ndarray] = []

    def capture_fit_predict(cfg, X_train, y_train, X_tests):
        value = float(y_train.sum())
        pred = {device: np.full(len(X_test), value) for device, X_test in X_tests.items()}
        captured.append(np.concatenate(list(pred.values())))
        return pred

    monkeypatch.setattr(pooled, "_fit_predict_pooled", capture_fit_predict)
    run_pooled_experiment(frames, cfg)
    expected = captured[0].copy()

    changed = {device: frame.copy() for device, frame in frames.items()}
    for frame in changed.values():
        frame.iloc[list(boundary), frame.columns.get_loc("soil_water")] += 10_000
    captured.clear()
    run_pooled_experiment(changed, cfg)

    np.testing.assert_array_equal(captured[0], expected)


def test_pooled_fleet_rows_include_fold_evidence():
    frames = {
        "s1": _synth_frame("2026-01-01", 400, 27.0, 1),
        "s2": _synth_frame("2026-01-01", 400, 18.0, 2),
    }
    cfg = IrrigationConfig(model="ridge", horizons_h=[6], n_folds=3)
    res = run_pooled_experiment(frames, cfg)
    fleet = res[res.device == "ALL"]
    assert fleet.skill_fold_median.notna().all()
    assert fleet.skill_fold_min.notna().all()
    persistence = fleet[fleet.model == "persistence"].iloc[0]
    assert persistence.skill_fold_median == 0.0
    assert persistence.skill_fold_min == 0.0


def test_pooled_ignores_undeclared_numeric_columns():
    frames = {
        "s1": _synth_frame("2026-01-01", 400, 27.0, 1),
        "s2": _synth_frame("2026-01-01", 400, 18.0, 2),
    }
    cfg = IrrigationConfig(
        model="ridge", features=["soil_water", "soil_temperature"], horizons_h=[6], n_folds=3
    )
    expected = run_pooled_experiment(frames, cfg)
    poisoned = {
        name: frame.assign(future_leak=np.arange(len(frame)) * 1e6)
        for name, frame in frames.items()
    }
    actual = run_pooled_experiment(poisoned, cfg)
    pd.testing.assert_frame_equal(actual, expected)


def test_pooled_returns_no_rows_for_too_little_training_data():
    frames = {
        "s1": _synth_frame("2026-01-01", 18, 27.0, 1),
        "s2": _synth_frame("2026-01-01", 18, 18.0, 2),
    }
    cfg = IrrigationConfig(model="ridge", horizons_h=[6], n_folds=2)
    result = run_pooled_experiment(frames, cfg)
    assert result.empty
