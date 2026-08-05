"""Tests for the D2 survival (time-to-event) layer."""

from __future__ import annotations

import numpy as np

from vine.d2_irrigation.stopping import crossing_curve, gaussian_increments
from vine.d2_irrigation.survival import (
    censored_brier_curve,
    censoring_survival,
    clock_survival,
    fit_hazard,
    hazard_design,
    hazard_survival,
    integrated_brier,
    kaplan_meier,
    person_periods,
    quantile_times,
    survival_curve_grid,
    survival_labels,
)


def _slow_labels(values, drop, max_h):
    """Loop reference for survival_labels: first event, censor at first gap."""
    n = len(values)
    out = []
    for i in range(n):
        if not np.isfinite(values[i]):
            continue
        time, event = None, False
        for j in range(1, max_h + 1):
            if i + j >= n or not np.isfinite(values[i + j]):
                time, event = j - 1, False
                break
            if values[i + j] <= values[i] - drop:
                time, event = j, True
                break
        if time is None:
            time, event = max_h + 1, False
        if time >= 1:
            out.append((i, time, event))
    return out


def test_survival_labels_match_slow_reference():
    rng = np.random.default_rng(7)
    values = 30.0 + np.cumsum(rng.normal(-0.02, 0.2, 400))
    values[rng.random(400) < 0.08] = np.nan
    idx, time, event = survival_labels(values, 0.3, 24)
    expected = _slow_labels(values, 0.3, 24)
    assert [(int(i), int(t), bool(e)) for i, t, e in zip(idx, time, event, strict=True)] == expected


def test_survival_labels_censors_at_gap_even_if_crossing_after():
    # Reading drops past the barrier at hour 3, but hour 2 is missing: the
    # crossing cannot be timed, so the row is censored at hour 1.
    values = np.array([30.0, 29.9, np.nan, 29.0, 28.6, 28.8])
    idx, time, event = survival_labels(values, 0.3, 4)
    assert idx[0] == 0 and time[0] == 1 and not event[0]
    # From index 3 the very next reading crosses.
    k = int(np.flatnonzero(idx == 3)[0])
    assert time[k] == 1 and event[k]


def test_survival_labels_full_window_survival_and_bad_args():
    values = np.full(10, 30.0)
    idx, time, event = survival_labels(values, 0.3, 4)
    # Early rows see four flat hours: known to survive the whole window.
    assert time[0] == 5 and not event[0]
    # The last row has zero observed future hours and is dropped.
    assert 9 not in idx
    for bad in ((0.0, 4), (0.3, 0)):
        try:
            survival_labels(values, *bad)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


def test_kaplan_meier_hand_example():
    # Times 1(event), 2(censored), 3(event), 4(survives past grid).
    time = np.array([1, 2, 3, 5])
    event = np.array([True, False, True, False])
    s = kaplan_meier(time, event, 4)
    # S(1) = 3/4; S(2) unchanged; S(3) = 3/4 * 1/2; S(4) unchanged.
    assert np.allclose(s, [0.75, 0.75, 0.375, 0.375])


def test_kaplan_meier_no_censoring_is_empirical_survival():
    time = np.array([1, 2, 2, 4, 5, 5])
    event = np.ones(6, dtype=bool)
    s = kaplan_meier(time, event, 5)
    emp = [(time > h).mean() for h in range(1, 6)]
    assert np.allclose(s, emp)


def test_censoring_survival_mirrors_km_with_roles_swapped():
    time = np.array([1, 2, 3, 5])
    event = np.array([True, False, True, False])
    g = censoring_survival(time, event, 4)
    # G(0) = 1; one censoring at hour 2 among three still at risk.
    assert g[0] == 1.0 and np.allclose(g[1:], [1.0, 2.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0])


def test_censored_brier_no_censoring_equals_plain_brier():
    rng = np.random.default_rng(3)
    max_h = 8
    t = rng.integers(1, max_h + 2, 200)  # max_h + 1 means survived the window
    e = t <= max_h
    surv = np.clip(rng.random((200, max_h)), 0.01, 0.99)
    g = censoring_survival(t, e, max_h)
    assert np.allclose(g, 1.0)  # nothing is censored inside the grid
    bs = censored_brier_curve(t, e, surv, g)
    for h in range(1, max_h + 1):
        alive = (t > h).astype(float)
        assert np.isclose(bs[h - 1], np.mean((alive - surv[:, h - 1]) ** 2))


def test_censored_brier_zero_for_perfect_prediction():
    max_h = 6
    t = np.array([2, 4, 7, 7])
    e = np.array([True, True, False, False])
    hours = np.arange(1, max_h + 1)
    surv = np.array([(hours < ti).astype(float) for ti in t])
    bs = censored_brier_curve(t, e, surv, censoring_survival(t, e, max_h))
    assert np.allclose(bs, 0.0)
    assert integrated_brier(bs) == 0.0


def test_ipcw_recovers_uncensored_brier_under_independent_censoring():
    rng = np.random.default_rng(11)
    n, max_h = 4000, 24
    t_true = rng.integers(1, 61, n)
    c = rng.integers(1, 81, n)
    obs = np.minimum(t_true, c)
    time = np.where(obs > max_h, max_h + 1, obs)
    event = (t_true <= c) & (obs <= max_h)
    time = np.where(event, t_true, time)
    hours = np.arange(1, max_h + 1)
    surv = np.tile(1.0 - hours / 70.0, (n, 1))
    bs = censored_brier_curve(time, event, surv, censoring_survival(time, event, max_h))
    plain = np.array([np.mean(((t_true > h) - surv[:, h - 1]) ** 2) for h in hours])
    assert np.abs(bs - plain).max() < 0.02


def test_survival_curve_grid_consistent_with_crossing_curve():
    inc = gaussian_increments(-0.05, 1.0, 256)
    grid, surv = survival_curve_grid(inc, 12)
    assert surv.shape == (12, len(grid))
    # Survival is nonincreasing in horizon at every level.
    assert (np.diff(surv, axis=0) <= 1e-12).all()
    levels = np.linspace(0.5, 6.0, 12)
    for h in (1, 5, 12):
        c_grid, c_probs = crossing_curve(inc, 0.0, h)
        expect = 1.0 - np.interp(levels, c_grid, c_probs)
        got = np.interp(levels, grid, surv[h - 1])
        assert np.allclose(got, expect, atol=2e-3)


def test_survival_curve_grid_unusable_inputs():
    grid, surv = survival_curve_grid(np.empty(0), 12)
    assert len(grid) == 0 and surv.size == 0


def test_clock_survival_step_and_edge_cases():
    s = clock_survival(-0.05, 0.3, 12)  # crosses at hour 6
    assert np.allclose(s, (np.arange(1, 13) < 6.0).astype(float))
    assert np.allclose(clock_survival(0.01, 0.3, 6), 1.0)
    assert np.isnan(clock_survival(np.nan, 0.3, 6)).all()


def test_quantile_times_hand_case():
    surv = np.array([0.95, 0.7, 0.4, 0.2])
    # Crossing prob: 0.05, 0.3, 0.6, 0.8.
    assert quantile_times(surv, (0.1, 0.5, 0.9)) == [2.0, 3.0, float("inf")]


def test_person_periods_hand_case():
    # Event at 2; censored at 3; survived a 4-hour window (time 5).
    time = np.array([2, 3, 5])
    event = np.array([True, False, False])
    rows, period, died = person_periods(time, event, 4)
    assert rows.tolist() == [0, 0, 1, 1, 1, 2, 2, 2, 2]
    assert period.tolist() == [1, 2, 1, 2, 3, 1, 2, 3, 4]
    assert died.tolist() == [0, 1, 0, 0, 0, 0, 0, 0, 0]
    r, p, d = person_periods(np.empty(0), np.empty(0, dtype=bool), 4)
    assert len(r) == 0 and len(p) == 0 and len(d) == 0


def test_fit_hazard_degenerate_and_nan_prediction():
    X = np.zeros((5, 9))
    assert fit_hazard(X, np.zeros(5)) is None
    assert fit_hazard(X, np.ones(5)) is None
    s = hazard_survival(None, np.zeros(3, dtype=int), np.zeros(3), np.ones(3), 6)
    assert s.shape == (3, 6) and np.isnan(s).all()


def test_hazard_model_learns_hour_of_day_timing():
    # Every row crosses at the first local noon after its decision hour. A
    # marginal KM curve cannot time that; the hazard model sees the diurnal
    # phase and should score far better on the same (uncensored) Brier.
    rng = np.random.default_rng(5)
    max_h = 24
    hod0 = rng.integers(0, 24, 600)
    time = ((12 - hod0 - 1) % 24) + 1  # hours until hod == 12, in 1..24
    event = np.ones(600, dtype=bool)
    m = np.full(600, -0.05)
    x = np.full(600, 3.0)
    rows, period, died = person_periods(time, event, max_h)
    X = hazard_design(period, (hod0[rows] + period) % 24, m[rows], x[rows])
    model = fit_hazard(X, died)
    assert model is not None
    surv = hazard_survival(model, hod0, m, x, max_h)
    assert surv.shape == (600, max_h)
    assert ((surv >= 0) & (surv <= 1)).all()
    assert (np.diff(surv, axis=1) <= 1e-12).all()
    g = np.ones(max_h + 1)
    ibs_hazard = integrated_brier(censored_brier_curve(time, event, surv, g))
    km = np.tile(kaplan_meier(time, event, max_h), (600, 1))
    ibs_km = integrated_brier(censored_brier_curve(time, event, km, g))
    assert ibs_hazard < 0.5 * ibs_km
