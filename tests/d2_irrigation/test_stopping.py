"""Tests for the D2 optimal-stopping decision layer."""

import math

import numpy as np
import pandas as pd

from vine.d2_irrigation.stopping import (
    _ndtri,
    cost_loss_expense,
    crossing_curve,
    crossing_probability_empirical,
    distance_to_threshold,
    economic_value,
    exercise_boundary,
    exercise_boundary_delayed,
    filtered_increments,
    gaussian_increments,
    increment_pool,
    standardized_pool,
)


def _hourly(values, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def _random_walk(n, mu=0.0, sigma=0.2, seed=3, start=30.0):
    rng = np.random.default_rng(seed)
    return _hourly(start + np.cumsum(rng.normal(mu, sigma, n)))


# --- increment pools ------------------------------------------------------


def test_increment_pool_excludes_gaps_never_bridges():
    y = _hourly([10.0, 11.0, np.nan, 20.0, 21.0])
    pool = increment_pool(y)
    # The +9 jump across the NaN hour never appears as an increment.
    assert list(pool) == [1.0, 1.0]


def test_increment_pool_empty_on_short_input():
    assert len(increment_pool(_hourly([10.0]))) == 0
    assert len(increment_pool(_hourly([]))) == 0


def test_standardized_pool_zero_mean_unit_scale():
    z = standardized_pool(_random_walk(1000))
    # Warmup rows are dropped, so slightly fewer values than deltas.
    assert 900 < len(z) < 1000
    assert abs(z.mean()) < 0.15
    assert 0.8 < z.std() < 1.25


def test_standardized_pool_empty_on_short_input():
    assert len(standardized_pool(_hourly(np.arange(10.0)))) == 0


# --- filtered increments --------------------------------------------------


def test_filtered_increments_exact_moments():
    z = standardized_pool(_random_walk(1000))
    inc = filtered_increments(z, mu=-0.05, sigma=0.3)
    assert len(inc) == 256
    # The quantile set is re-standardized, so the moments are exact.
    assert np.isclose(inc.mean(), -0.05, atol=1e-12)
    assert np.isclose(inc.std(), 0.3, atol=1e-12)


def test_filtered_increments_unusable_inputs_give_empty():
    z = standardized_pool(_random_walk(1000))
    assert len(filtered_increments(z[:47], mu=0.0, sigma=0.3)) == 0  # pool < 48
    assert len(filtered_increments(z, mu=0.0, sigma=0.0)) == 0
    assert len(filtered_increments(z, mu=0.0, sigma=-1.0)) == 0
    assert len(filtered_increments(z, mu=0.0, sigma=float("nan"))) == 0
    assert len(filtered_increments(z, mu=float("nan"), sigma=0.3)) == 0


# --- gaussian discretization ----------------------------------------------


def test_ndtri_matches_known_quantiles():
    assert abs(_ndtri(0.5)) < 1e-6
    assert abs(_ndtri(0.975) - 1.959964) < 1e-6
    assert abs(_ndtri(0.025) + 1.959964) < 1e-6


def test_gaussian_increments_moments():
    inc = gaussian_increments(-0.02, 0.1)
    assert len(inc) == 256
    assert np.isclose(inc.mean(), -0.02, atol=1e-9)
    # Quantile midpoints thin the extreme tails a touch, so the std sits
    # just below sigma.
    assert np.isclose(inc.std(), 0.1, atol=1e-3)
    assert np.all(np.diff(inc) >= 0)


def test_gaussian_increments_unusable_sigma_gives_empty():
    assert len(gaussian_increments(0.0, 0.0)) == 0
    assert len(gaussian_increments(0.0, float("nan"))) == 0
    assert len(gaussian_increments(float("nan"), 0.1)) == 0


# --- empirical crossing probability ---------------------------------------


def test_crossing_probability_one_at_or_below_threshold():
    inc = gaussian_increments(-0.02, 0.1)
    p = crossing_probability_empirical(np.array([0.0, -0.5]), 0.0, 6, inc)
    assert list(p) == [1.0, 1.0]


def test_crossing_curve_decreasing_in_starting_level():
    inc = gaussian_increments(-0.02, 0.1)
    grid, probs = crossing_curve(inc, 0.0, 24)
    assert len(grid) == len(probs) > 0
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0)
    assert np.all(np.diff(probs) <= 1e-9)


def test_crossing_probability_monotone_in_horizon():
    inc = gaussian_increments(-0.02, 0.1)
    ps = [float(crossing_probability_empirical(0.3, 0.0, h, inc)[0]) for h in (6, 12, 24, 48)]
    assert all(a <= b for a, b in zip(ps, ps[1:], strict=False))
    assert 0.0 < ps[0] < ps[-1] < 1.0


def test_crossing_probability_matches_monte_carlo():
    # The pin on discrete-monitoring semantics: the DP prices a walk that is
    # checked once per hour, so it must match a Monte Carlo of the discretely
    # monitored walk, and sit below the continuous closed form.
    mu, sigma, thr = -0.02, 0.1, 0.0
    inc = gaussian_increments(mu, sigma)
    rng = np.random.default_rng(0)
    for h in (6, 24):
        steps = rng.normal(mu, sigma, size=(200_000, h))
        path_min = np.minimum.accumulate(np.cumsum(steps, axis=1), axis=1)[:, -1]
        for level in (0.3, 0.6):
            mc = float((level + path_min <= thr).mean())
            dp = float(crossing_probability_empirical(level, thr, h, inc)[0])
            assert abs(dp - mc) < 0.005


def test_crossing_unusable_inputs():
    grid, probs = crossing_curve(np.empty(0), 0.0, 24)
    assert len(grid) == 0 and len(probs) == 0
    grid, probs = crossing_curve(gaussian_increments(0.0, 0.1), 0.0, 0)
    assert len(grid) == 0 and len(probs) == 0
    p = crossing_probability_empirical(np.array([0.3, 0.6]), 0.0, 24, np.empty(0))
    assert np.isnan(p).all()
    inc = gaussian_increments(0.0, 0.1)
    p = crossing_probability_empirical(np.array([0.3, np.nan]), 0.0, 24, inc)
    assert not math.isnan(p[0]) and math.isnan(p[1])


# --- exercise boundary ----------------------------------------------------


def test_exercise_boundary_shape_and_nan_cases():
    inc = gaussian_increments(-0.02, 0.1)
    b = exercise_boundary(inc, 0.0, 24, 0.3, grid_hi=2.0)
    assert b.shape == (24,)
    for bad_ratio in (0.0, 1.0, 1.5, -0.1):
        assert np.isnan(exercise_boundary(inc, 0.0, 24, bad_ratio, grid_hi=2.0)).all()
    assert np.isnan(exercise_boundary(np.empty(0), 0.0, 24, 0.3, grid_hi=2.0)).all()


def test_exercise_boundary_nondecreasing_and_above_threshold():
    inc = gaussian_increments(-0.05, 0.1)
    b = exercise_boundary(inc, 0.0, 24, 0.3, grid_hi=3.0)
    # More exposure hours make waiting riskier, so the trigger only rises.
    assert np.all(np.diff(b) >= -1e-9)
    # Downward drift with cost_ratio < 1 buys headroom above the barrier,
    # the early-exercise premium.
    assert np.all(b > 0.0)


def test_exercise_boundary_one_step_identity():
    # With 1 hour remaining the boundary solves
    # P(one step to at or below threshold) = cost_ratio.
    inc = gaussian_increments(-0.02, 0.1)
    for ratio in (0.2, 0.5):
        b1 = float(exercise_boundary(inc, 0.0, 24, ratio, grid_hi=2.0)[0])
        one_step = float((b1 + inc <= 0.0).mean())
        assert abs(one_step - ratio) < 0.02


def test_exercise_boundary_lower_for_higher_cost_ratio():
    inc = gaussian_increments(-0.02, 0.1)
    b_cheap = exercise_boundary(inc, 0.0, 24, 0.3, grid_hi=2.0)
    b_dear = exercise_boundary(inc, 0.0, 24, 0.6, grid_hi=2.0)
    assert np.all(b_dear <= b_cheap + 1e-9)


# --- delayed exercise boundary --------------------------------------------


def test_delayed_boundary_zero_delay_matches_instant():
    # delay_h = 0 makes the exercise value the constant cost_ratio, so the
    # recursion must reduce exactly to the instant-response boundary.
    inc = gaussian_increments(-0.05, 0.1)
    for ratio in (0.1, 0.3):
        b0 = exercise_boundary(inc, 0.0, 24, ratio, grid_hi=3.0)
        bd = exercise_boundary_delayed(inc, 0.0, 24, ratio, delay_h=0, grid_hi=3.0)
        assert np.allclose(bd, b0, rtol=0.0, atol=1e-10)


def test_delayed_boundary_nondecreasing_in_delay():
    # A slower response means the level keeps walking while the crew works, so
    # at the longest exposure the trigger can only rise with the lead time.
    inc = gaussian_increments(-0.05, 0.1)
    last = [
        float(exercise_boundary_delayed(inc, 0.0, 24, 0.1, d, grid_hi=3.0)[-1])
        for d in (0, 2, 6, 12)
    ]
    assert all(a <= b + 1e-9 for a, b in zip(last, last[1:], strict=False))
    # The effect is material, an order of magnitude above grid noise.
    assert last[-1] > last[0] + 0.5


def test_delayed_boundary_one_hour_identity():
    # With one hour remaining and at least one hour of lead time the water
    # cannot land inside the window: exposure is min(d, 1) = 1 either way, so
    # exercise = c + Q_1 > Q_1 = wait and the boundary sits at the barrier.
    inc = gaussian_increments(-0.05, 0.1)
    for d in (1, 3, 24):
        b = exercise_boundary_delayed(inc, 0.0, 24, 0.3, d, grid_hi=3.0)
        assert b[0] == 0.0


def test_delayed_boundary_monotone_in_k_and_nan_cases():
    inc = gaussian_increments(-0.05, 0.1)
    b = exercise_boundary_delayed(inc, 0.0, 24, 0.3, 6, grid_hi=3.0)
    assert b.shape == (24,)
    # More exposure hours make waiting riskier, so the trigger only rises.
    assert np.all(np.diff(b) >= -1e-9)
    for bad_ratio in (0.0, 1.0, 1.5, -0.1):
        assert np.isnan(exercise_boundary_delayed(inc, 0.0, 24, bad_ratio, 6, grid_hi=3.0)).all()
    assert np.isnan(exercise_boundary_delayed(np.empty(0), 0.0, 24, 0.3, 6, grid_hi=3.0)).all()


# --- distance to threshold ------------------------------------------------


def test_distance_to_threshold_value_and_nan():
    assert math.isclose(distance_to_threshold(30.0, 25.0, 0.5, 4), 5.0)
    assert math.isnan(distance_to_threshold(30.0, 25.0, 0.0, 4))
    assert math.isnan(distance_to_threshold(30.0, 25.0, float("nan"), 4))
    assert math.isnan(distance_to_threshold(30.0, 25.0, 0.5, 0))


# --- cost-loss economics --------------------------------------------------


def test_cost_loss_expense_hand_computed():
    alert = np.array([True, True, False, False])
    event = np.array([True, False, True, False])
    # Expenses per row: alpha, alpha, 1 (miss), 0 -> mean 0.45.
    assert math.isclose(cost_loss_expense(alert, event, 0.4), 0.45)
    assert math.isnan(cost_loss_expense(np.array([]), np.array([]), 0.4))


def test_economic_value_perfect_and_trivial_rules():
    event = np.array([True, False, True, False])
    alpha = 0.3
    assert math.isclose(economic_value(event.copy(), event, alpha), 1.0)
    always = np.ones(4, dtype=bool)
    never = np.zeros(4, dtype=bool)
    assert economic_value(always, event, alpha) <= 0.0
    assert economic_value(never, event, alpha) <= 0.0


def test_economic_value_degenerate_cases():
    assert math.isnan(economic_value(np.array([]), np.array([]), 0.3))
    # Base rate 0 or 1 makes the reference strategies coincide.
    alert = np.array([True, False, True, False])
    assert math.isnan(economic_value(alert, np.zeros(4, dtype=bool), 0.3))
    assert math.isnan(economic_value(alert, np.ones(4, dtype=bool), 0.3))
