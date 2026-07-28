"""Tests for the D5 reporting API (fold ids, fair holdout mask, detailed report)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vine.d5_evaluation.reporting import (
    build_report,
    fold_assignment,
    fold_masks,
    holdout_mask,
)

N = 40
N_FOLDS = 4
HOLDOUT_START = 20  # n // 2, the default min_train for n=40


def _index() -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=N, freq="1h", tz="UTC")


def _ramp() -> pd.Series:
    """A linear ramp: shift(1) has a constant, exactly-known error of 1."""
    return pd.Series(np.arange(N, dtype=float), index=_index())


def _clean_preds(y: pd.Series) -> dict[str, pd.Series]:
    """persistence (mae=1), perfect (mae=0), bad (mae=3) — all vs `y`."""
    return {
        "persistence": y.shift(1),
        "perfect": y.copy(),
        "bad": y - 3.0,
    }


# --------------------------------------------------------------------------
# fold_assignment / fold_masks
# --------------------------------------------------------------------------


def test_fold_assignment_matches_expanding_splits_layout():
    ids = fold_assignment(N, N_FOLDS)
    assert (ids[:HOLDOUT_START] == -1).all()
    # 4 folds of 5 rows each, in order, no gaps or overlap (see expanding_splits)
    assert ids[20:25].tolist() == [0] * 5
    assert ids[25:30].tolist() == [1] * 5
    assert ids[30:35].tolist() == [2] * 5
    assert ids[35:40].tolist() == [3] * 5


def test_fold_assignment_is_deterministic():
    a = fold_assignment(N, N_FOLDS)
    b = fold_assignment(N, N_FOLDS)
    assert np.array_equal(a, b)


def test_fold_assignment_propagates_expanding_splits_errors():
    with pytest.raises(ValueError, match="not enough rows"):
        fold_assignment(8, n_folds=5)


def test_fold_masks_partition_the_holdout_exactly():
    idx = _index()
    masks = fold_masks(idx, N_FOLDS)
    assert len(masks) == N_FOLDS
    # every fold mask is disjoint from every other
    stacked = np.vstack([m.to_numpy() for m in masks])
    assert (stacked.sum(axis=0) <= 1).all()
    # union of all fold masks is exactly the holdout region
    ids = fold_assignment(N, N_FOLDS)
    union = stacked.any(axis=0)
    assert np.array_equal(union, ids >= 0)
    # each mask matches its fold's row count from fold_assignment
    for i, m in enumerate(masks):
        assert int(m.sum()) == int((ids == i).sum())


# --------------------------------------------------------------------------
# holdout_mask
# --------------------------------------------------------------------------


def test_holdout_mask_excludes_pre_holdout_rows():
    y = _ramp()
    preds = _clean_preds(y)
    valid = holdout_mask(y, preds)
    assert int(valid.sum()) == N - HOLDOUT_START
    assert not valid.iloc[:HOLDOUT_START].any()
    assert valid.iloc[HOLDOUT_START:].all()


def test_holdout_mask_is_fair_when_one_prediction_has_a_gap():
    y = _ramp()
    preds = _clean_preds(y)
    gap_ts = y.index[22]
    preds["bad"] = preds["bad"].copy()
    preds["bad"].loc[gap_ts] = np.nan

    valid = holdout_mask(y, preds)
    assert int(valid.sum()) == N - HOLDOUT_START - 1
    assert not valid.loc[gap_ts]
    # every other holdout row is still included for every model
    other_holdout = y.index[HOLDOUT_START:].difference([gap_ts])
    assert valid.loc[other_holdout].all()


def test_holdout_mask_rejects_empty_preds():
    y = _ramp()
    with pytest.raises(ValueError, match="empty"):
        holdout_mask(y, {})


def test_holdout_mask_rejects_misaligned_prediction_index():
    y = _ramp()
    misaligned = pd.Series(np.arange(N, dtype=float))  # default RangeIndex, not y's index
    with pytest.raises(ValueError, match="not aligned"):
        holdout_mask(y, {"persistence": misaligned})


# --------------------------------------------------------------------------
# build_report
# --------------------------------------------------------------------------


def test_build_report_aggregate_mae_rmse_and_skill():
    y = _ramp()
    preds = _clean_preds(y)
    report = build_report(y, preds, irrigate_below=23.0)
    agg = report["aggregate"]

    assert agg.loc["persistence", "mae"] == pytest.approx(1.0)
    assert agg.loc["persistence", "rmse"] == pytest.approx(1.0)
    assert agg.loc["persistence", "skill_vs_persistence"] == pytest.approx(0.0)

    assert agg.loc["perfect", "mae"] == pytest.approx(0.0)
    assert agg.loc["perfect", "rmse"] == pytest.approx(0.0)
    assert agg.loc["perfect", "skill_vs_persistence"] == pytest.approx(1.0)

    assert agg.loc["bad", "mae"] == pytest.approx(3.0)
    assert agg.loc["bad", "rmse"] == pytest.approx(3.0)
    assert agg.loc["bad", "skill_vs_persistence"] == pytest.approx(-2.0)

    assert agg.loc["persistence", "n"] == N - HOLDOUT_START


def test_build_report_full_binary_metrics_match_hand_computed():
    """irrigate_below=23 over holdout y in [20, 39]: event is y < 23 (y in {20,21,22})."""
    y = _ramp()
    preds = _clean_preds(y)
    agg = build_report(y, preds, irrigate_below=23.0)["aggregate"]

    perfect = agg.loc["perfect"]
    assert perfect["true_positive"] == 3
    assert perfect["false_positive"] == 0
    assert perfect["false_negative"] == 0
    assert perfect["precision"] == pytest.approx(1.0)
    assert perfect["recall"] == pytest.approx(1.0)
    assert perfect["f1"] == pytest.approx(1.0)
    assert perfect["prevalence"] == pytest.approx(3 / 20)
    assert perfect["alert_rate"] == pytest.approx(3 / 20)

    pers = agg.loc["persistence"]  # predicts y - 1 < 23 <=> y < 24 -> {20,21,22,23}
    assert pers["true_positive"] == 3
    assert pers["false_positive"] == 1
    assert pers["false_negative"] == 0
    assert pers["precision"] == pytest.approx(0.75)
    assert pers["recall"] == pytest.approx(1.0)
    assert pers["specificity"] == pytest.approx(16 / 17)

    bad = agg.loc["bad"]  # predicts y - 3 < 23 <=> y < 26 -> {20,...,25}
    assert bad["true_positive"] == 3
    assert bad["false_positive"] == 3
    assert bad["false_negative"] == 0
    assert bad["precision"] == pytest.approx(0.5)
    assert bad["recall"] == pytest.approx(1.0)
    assert bad["f1"] == pytest.approx(2 / 3)
    assert bad["specificity"] == pytest.approx(14 / 17)
    assert bad["alert_rate"] == pytest.approx(6 / 20)


def test_build_report_per_fold_rows_and_constant_skills():
    y = _ramp()
    preds = _clean_preds(y)
    per_fold = build_report(y, preds, irrigate_below=23.0, n_folds=N_FOLDS)["per_fold"]

    assert set(per_fold["model"]) == {"persistence", "perfect", "bad"}
    assert sorted(per_fold["fold"].unique().tolist()) == [0, 1, 2, 3]
    assert len(per_fold) == 3 * N_FOLDS  # one row per (model, fold)
    assert (per_fold["n"] == 5).all()  # 20 holdout rows / 4 folds

    def skills(model: str) -> list[float]:
        return per_fold.loc[per_fold["model"] == model, "skill_vs_persistence"].tolist()

    assert skills("persistence") == pytest.approx([0.0] * N_FOLDS)
    assert skills("perfect") == pytest.approx([1.0] * N_FOLDS)
    assert skills("bad") == pytest.approx([-2.0] * N_FOLDS)


def test_build_report_predictions_frame_has_expected_shape_and_fold_ids():
    y = _ramp()
    preds = _clean_preds(y)
    predictions = build_report(y, preds, irrigate_below=23.0, n_folds=N_FOLDS)["predictions"]

    assert set(predictions.columns) == {"fold", "y_true", "persistence", "perfect", "bad"}
    assert len(predictions) == N - HOLDOUT_START
    assert (predictions["y_true"] == y.iloc[HOLDOUT_START:]).all()
    expected_fold_ids = fold_assignment(N, N_FOLDS)[HOLDOUT_START:]
    assert predictions["fold"].tolist() == expected_fold_ids.tolist()


def test_build_report_excludes_gap_rows_identically_for_every_model():
    y = _ramp()
    preds = _clean_preds(y)
    gap_ts = y.index[22]
    preds["bad"] = preds["bad"].copy()
    preds["bad"].loc[gap_ts] = np.nan

    report = build_report(y, preds, irrigate_below=23.0)
    assert (report["aggregate"]["n"] == N - HOLDOUT_START - 1).all()
    assert gap_ts not in report["predictions"].index


def test_build_report_missing_baseline_raises():
    y = _ramp()
    preds = _clean_preds(y)
    del preds["persistence"]
    with pytest.raises(ValueError, match="baseline"):
        build_report(y, preds, irrigate_below=23.0)


def test_build_report_no_scorable_rows_raises():
    y = _ramp()
    preds = {
        "persistence": pd.Series(np.nan, index=y.index),
        "perfect": pd.Series(np.nan, index=y.index),
    }
    with pytest.raises(ValueError, match="no scorable rows"):
        build_report(y, preds, irrigate_below=23.0)


def test_build_report_is_deterministic():
    y = _ramp()
    preds = _clean_preds(y)
    r1 = build_report(y, preds, irrigate_below=23.0)
    r2 = build_report(y, preds, irrigate_below=23.0)
    pd.testing.assert_frame_equal(r1["aggregate"], r2["aggregate"])
    pd.testing.assert_frame_equal(r1["per_fold"], r2["per_fold"])
    pd.testing.assert_frame_equal(r1["predictions"], r2["predictions"])


def test_build_report_custom_baseline_and_min_train():
    y = _ramp()
    preds = _clean_preds(y)
    # "bad" as the baseline: persistence (mae=1) now beats it (baseline mae=3)
    report = build_report(y, preds, irrigate_below=23.0, baseline="bad", min_train=30)
    agg = report["aggregate"]
    assert agg.loc["persistence", "n"] == N - 30
    assert agg.loc["persistence", "skill_vs_persistence"] == pytest.approx(1 - 1 / 3)
    assert agg.loc["bad", "skill_vs_persistence"] == pytest.approx(0.0)
