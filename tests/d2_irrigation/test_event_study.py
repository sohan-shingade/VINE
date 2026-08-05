"""Event mask and subset metrics for the D2 event-conditioned evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.event_study import (
    event_error_share,
    event_mask,
    run_event_study,
    subset_metrics,
)


def _index(n: int, start: str = "2026-03-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="1h", tz="UTC")


def test_event_mask_covers_window_plus_trailing_hours():
    idx = pd.DatetimeIndex(_index(100))
    events = pd.DataFrame({"start": [idx[10]], "end": [idx[12]]})
    mask = event_mask(idx, events, trailing_h=24)
    expected = pd.Series(False, index=idx)
    expected.iloc[10 : 12 + 24 + 1] = True  # start..end plus 24 trailing hours
    pd.testing.assert_series_equal(mask, expected)
    assert int(mask.sum()) == 27


def test_event_mask_empty_events_all_false():
    idx = pd.DatetimeIndex(_index(50))
    events = pd.DataFrame(columns=["start", "end"])
    assert not event_mask(idx, events).any()


def test_event_mask_overlapping_events_union():
    idx = pd.DatetimeIndex(_index(100))
    events = pd.DataFrame({"start": [idx[10], idx[20]], "end": [idx[12], idx[22]]})
    mask = event_mask(idx, events, trailing_h=24)
    # Windows 10..36 and 20..46 union into 10..46.
    assert mask.iloc[10:47].all()
    assert not mask.iloc[:10].any()
    assert not mask.iloc[47:].any()


def test_subset_metrics_math_and_persistence_zero_skill():
    idx = _index(10)
    y = pd.Series(0.0, index=idx)
    in_event = pd.Series([True] * 4 + [False] * 6, index=idx)
    valid = pd.Series(True, index=idx)
    preds = {
        "persistence": pd.Series([2.0] * 4 + [1.0] * 6, index=idx),
        "challenger": pd.Series(1.0, index=idx),
    }
    table = subset_metrics(y, preds, in_event, valid)

    def cell(model: str, subset: str) -> pd.Series:
        return table[(table.model == model) & (table.subset == subset)].iloc[0]

    assert cell("persistence", "event").n == 4
    assert cell("persistence", "quiet").n == 6
    assert cell("persistence", "all").n == 10
    # Persistence scores exactly zero skill against itself on every subset.
    for subset in ("event", "quiet", "all"):
        assert cell("persistence", subset).skill_vs_persistence == 0.0
    assert np.isclose(cell("persistence", "event").mae, 2.0)
    assert np.isclose(cell("challenger", "event").mae, 1.0)
    assert np.isclose(cell("challenger", "event").skill_vs_persistence, 0.5)
    assert np.isclose(cell("challenger", "quiet").skill_vs_persistence, 0.0)
    assert np.isclose(cell("challenger", "all").skill_vs_persistence, 1.0 - 1.0 / 1.4)


def test_subset_metrics_rows_outside_valid_never_scored():
    idx = _index(10)
    y = pd.Series(0.0, index=idx)
    in_event = pd.Series(True, index=idx)
    valid = pd.Series([False] * 5 + [True] * 5, index=idx)
    preds = {"persistence": pd.Series([100.0] * 5 + [1.0] * 5, index=idx)}
    table = subset_metrics(y, preds, in_event, valid)
    event_row = table[(table.model == "persistence") & (table.subset == "event")].iloc[0]
    assert event_row.n == 5
    assert np.isclose(event_row.mae, 1.0)  # the 100.0 rows are invalid, excluded


def test_subset_metrics_empty_event_subset_yields_nan_not_error():
    idx = _index(10)
    y = pd.Series(0.0, index=idx)
    in_event = pd.Series(False, index=idx)
    valid = pd.Series(True, index=idx)
    preds = {"persistence": pd.Series(1.0, index=idx)}
    table = subset_metrics(y, preds, in_event, valid)
    event_row = table[table.subset == "event"].iloc[0]
    assert event_row.n == 0
    assert np.isnan(event_row.mae)
    quiet_row = table[table.subset == "quiet"].iloc[0]
    all_row = table[table.subset == "all"].iloc[0]
    assert quiet_row.n == all_row.n == 10


def test_event_error_share_fraction():
    idx = _index(10)
    y = pd.Series(0.0, index=idx)
    pers = pd.Series([2.0] * 4 + [1.0] * 6, index=idx)
    in_event = pd.Series([True] * 4 + [False] * 6, index=idx)
    valid = pd.Series(True, index=idx)
    assert np.isclose(event_error_share(y, pers, in_event, valid), 8.0 / 14.0)
    # Zero total error (a solved series) reports share 0 rather than dividing.
    assert event_error_share(y, y.copy(), in_event, valid) == 0.0


def test_run_event_study_smoke_schema_and_masks():
    rng = np.random.default_rng(0)
    idx = _index(400)
    soil = pd.Series(30.0 + np.cumsum(rng.normal(0, 0.05, 400)), index=idx)
    frame = pd.DataFrame(
        {
            "soil_water": soil,
            "soil_temperature": 15.0 + rng.normal(0, 1, 400),
            "soil_conductivity": 100.0 + rng.normal(0, 5, 400),
        }
    )
    cfg = IrrigationConfig(model="naive", horizons_h=[6], n_folds=3)
    events = pd.DataFrame({"start": [idx[300]], "end": [idx[303]]})
    results, shares = run_event_study(frame, cfg, events, trailing_h=24)

    assert set(results.model) == {"persistence", "diurnal_drift"}
    assert set(results.subset) == {"event", "quiet", "all"}
    assert list(results.columns) == [
        "model",
        "horizon_h",
        "subset",
        "n",
        "mae",
        "rmse",
        "skill_vs_persistence",
    ]
    # The event window is hours 300 to 327 inclusive, all inside the holdout.
    n_event = results[(results.subset == "event") & (results.model == "persistence")].iloc[0].n
    assert n_event == 28
    n_all = results[(results.subset == "all") & (results.model == "persistence")].iloc[0].n
    n_quiet = results[(results.subset == "quiet") & (results.model == "persistence")].iloc[0].n
    assert n_event + n_quiet == n_all
    for subset in ("event", "quiet", "all"):
        row = results[(results.model == "persistence") & (results.subset == subset)].iloc[0]
        assert row.skill_vs_persistence == 0.0
    assert 0.0 <= shares[6] <= 1.0
