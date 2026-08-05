"""Gate decision, hybrid combination, and causal selection for the D2 rain-gated hybrid."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.gated import (
    RESULT_COLUMNS,
    gate_fired,
    hybrid_predict,
    run_gated,
    select_threshold,
)


def _index(n: int, start: str = "2026-03-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="1h", tz="UTC")


def test_gate_fired_threshold_boundary_and_nan():
    idx = _index(4)
    precip = pd.Series([0.4, 1.0, 3.0, np.nan], index=idx)
    fired = gate_fired(precip, 1.0)
    assert list(fired) == [False, True, True, False]  # NaN forecast never fires


def test_hybrid_below_threshold_is_bitwise_persistence():
    idx = _index(6)
    # Awkward float values so an accidental recomputation would show up.
    pers = pd.Series([np.pi, 0.1 + 0.2, 1.0 / 3.0, 27.700000000000003, 1e-17, 30.0], index=idx)
    wb = pd.Series(99.0, index=idx)
    fired = pd.Series(False, index=idx)
    out = hybrid_predict(pers, wb, fired)
    assert out.to_numpy().tobytes() == pers.to_numpy().tobytes()


def test_hybrid_above_threshold_takes_water_balance():
    idx = _index(4)
    pers = pd.Series(30.0, index=idx)
    wb = pd.Series([31.0, 32.0, 33.0, 34.0], index=idx)
    fired = pd.Series([False, True, True, False], index=idx)
    out = hybrid_predict(pers, wb, fired)
    assert list(out) == [30.0, 32.0, 33.0, 30.0]


def test_hybrid_fired_but_wb_missing_falls_back_to_persistence():
    idx = _index(3)
    pers = pd.Series([30.0, 31.0, 32.0], index=idx)
    wb = pd.Series([np.nan, 40.0, np.nan], index=idx)
    fired = pd.Series(True, index=idx)
    out = hybrid_predict(pers, wb, fired)
    assert list(out) == [30.0, 40.0, 32.0]


def _selection_fixture() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """A case where firing at 1.0 mm is exactly right.

    Rows with forecast precip >= 1.0 carry a real jump that the stubbed
    water-balance forecast nails; rows with lighter forecast precip carry no
    jump, and the stub is badly wrong there. Firing at 0.5 applies the bad
    correction to drizzle rows; firing at 2.0 or 5.0 misses real jumps.
    """
    n = 200
    idx = _index(n)
    precip = pd.Series(np.resize([0.0, 0.7, 1.5, 3.0], n), index=idx, dtype=float)
    y = pd.Series(np.where(precip >= 1.0, 32.0, 30.0), index=idx, dtype=float)
    X = pd.DataFrame({"soil_water": 30.0, "precip_next_6h": precip, "et0_next_6h": 0.1})
    X.index = idx
    pers = pd.Series(30.0, index=idx)
    return X, y, pers


def _stub_wb(X: pd.DataFrame, y: pd.Series) -> object:
    """fit_predict stub: perfect where forecast precip >= 1.0, off by 5 elsewhere."""

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        p = X_test["precip_next_6h"].to_numpy()
        truth = y.loc[X_test.index].to_numpy()
        return np.where(p >= 1.0, truth, truth + 5.0)

    return fit_predict


def test_select_threshold_picks_the_strictly_best_candidate():
    X, y, pers = _selection_fixture()
    chosen = select_threshold(
        X, y, pers, _stub_wb(X, y), slice(0, 160), 6, thresholds_mm=(0.5, 1.0, 2.0, 5.0)
    )
    assert chosen == 1.0


def test_select_threshold_tie_goes_to_the_largest_threshold():
    X, y, pers = _selection_fixture()

    def all_nan(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        return np.full(len(X_test), np.nan)

    # Every candidate degenerates to persistence, so the least-firing wins.
    chosen = select_threshold(
        X, y, pers, all_nan, slice(0, 160), 6, thresholds_mm=(0.5, 1.0, 2.0, 5.0)
    )
    assert chosen == 5.0


def test_select_threshold_never_reads_past_train_stop():
    X, y, pers = _selection_fixture()
    stub = _stub_wb(X, y)
    clean = select_threshold(X, y, pers, stub, slice(0, 160), 6)
    poisoned_y = y.copy()
    poisoned_y.iloc[160:] += 1000.0
    poisoned_X = X.copy()
    poisoned_X.iloc[160:] = 1e9
    poisoned = select_threshold(
        poisoned_X, poisoned_y, pers, _stub_wb(poisoned_X, poisoned_y), slice(0, 160), 6
    )
    assert poisoned == clean


def _synthetic_frame(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = _index(n)
    soil = pd.Series(30.0 + np.cumsum(rng.normal(0, 0.05, n)), index=idx)
    return pd.DataFrame(
        {
            "soil_water": soil,
            "soil_temperature": 15.0 + rng.normal(0, 1, n),
            "soil_conductivity": 100.0 + rng.normal(0, 5, n),
        }
    )


def _synthetic_vintages(n: int, lags: tuple[int, ...] = (1,), storm_at: int = 300) -> pd.DataFrame:
    idx = pd.date_range("2026-03-01", periods=n, freq="1h")  # tz-naive like Open-Meteo
    frame = pd.DataFrame(index=idx)
    precip = np.zeros(n)
    precip[storm_at : storm_at + 12] = 1.5  # a storm the archived forecast saw coming
    for lag in lags:
        frame[f"precip_mm_prev{lag}"] = precip
        frame[f"et0_mm_prev{lag}"] = 0.1
    return frame


def _cfg(horizons: list[int], n_folds: int = 3) -> IrrigationConfig:
    return IrrigationConfig(
        model="water_balance",
        features=["soil_water"],
        horizons_h=horizons,
        n_folds=n_folds,
        forecast_features=True,
        weather_source="vintage",
    )


def test_run_gated_smoke_schema_and_gate_bookkeeping():
    frame = _synthetic_frame(400)
    vintages = _synthetic_vintages(400)
    events = pd.DataFrame({"start": [frame.index[300]], "end": [frame.index[303]]})
    results, selected = run_gated(frame, _cfg([6]), events, vintages=vintages)

    assert list(results.columns) == RESULT_COLUMNS
    assert set(results.model) == {"persistence", "gated_wb", "gated_wb_selected"}
    assert set(results.subset) == {"all", "event", "quiet", "fired"}
    # Persistence is never gated: no fired rows and zero skill against itself.
    pers_rows = results[results.model == "persistence"]
    assert set(pers_rows.subset) == {"all", "event", "quiet"}
    assert (pers_rows[pers_rows.n > 0].skill_vs_persistence == 0.0).all()
    assert (pers_rows[pers_rows.n > 0].skill_fold_min == 0.0).all()
    # Four fixed thresholds plus the per-fold selection, all bounded fractions.
    gated = results[results.model == "gated_wb"]
    assert sorted(gated.threshold_mm.unique()) == [0.5, 1.0, 2.0, 5.0]
    assert results[results.model != "persistence"].gate_fired_frac.between(0.0, 1.0).all()
    assert list(selected) == [6]
    assert len(selected[6]) == 3
    assert set(selected[6]) <= {0.5, 1.0, 2.0, 5.0}
    # The 1.5 mm/h storm fires the 0.5 mm gate somewhere in the holdout.
    fired_row = results[
        (results.model == "gated_wb") & (results.threshold_mm == 0.5) & (results.subset == "all")
    ].iloc[0]
    assert fired_row.gate_fired_frac > 0.0


def test_run_gated_unfired_rows_match_persistence_via_high_threshold():
    # An 18 mm threshold can never fire on the 1.5 mm/h synthetic storm, so
    # the gated model must reproduce persistence's metrics exactly.
    frame = _synthetic_frame(400)
    vintages = _synthetic_vintages(400)
    events = pd.DataFrame(columns=["start", "end"])
    results, _ = run_gated(frame, _cfg([6]), events, vintages=vintages, thresholds_mm=(0.5, 18.0))
    never = results[
        (results.model == "gated_wb") & (results.threshold_mm == 18.0) & (results.subset == "all")
    ].iloc[0]
    pers = results[(results.model == "persistence") & (results.subset == "all")].iloc[0]
    assert never.gate_fired_frac == 0.0
    assert never.mae == pers.mae
    assert never.rmse == pers.rmse
    assert never.skill_vs_persistence == 0.0


def test_run_gated_ignores_vintages_issued_after_the_origin():
    # Causality: at h=48 only the previous_day2 vintage is admissible; the
    # previous_day1 run can be issued up to a day after the origin. Poisoning
    # prev1 must therefore change nothing in the 48 h evaluation.
    frame = _synthetic_frame(500)
    vintages = _synthetic_vintages(500, lags=(1, 2))
    events = pd.DataFrame({"start": [frame.index[300]], "end": [frame.index[303]]})
    cfg = _cfg([48])
    clean, clean_selected = run_gated(frame, cfg, events, vintages=vintages)

    poisoned_vintages = vintages.copy()
    poisoned_vintages["precip_mm_prev1"] = 1e9
    poisoned_vintages["et0_mm_prev1"] = 1e9
    poisoned, poisoned_selected = run_gated(frame, cfg, events, vintages=poisoned_vintages)

    pd.testing.assert_frame_equal(poisoned, clean)
    assert poisoned_selected == clean_selected
