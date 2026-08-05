"""Optimal-stopping decision layer for the irrigation alert (D2).

The forecasting ladder is closed: fifteen challenger families failed to beat
persistence on the level. `first_passage` already changed the question from
"what will the level be" to "will the level cross the trigger", pricing it as a
barrier option under a Gaussian random walk. This module changes the question
once more, from probability to decision, and drops the Gaussian assumption that
the closed form needs.

Three pieces, each borrowed from a different discipline:

1. **Historical simulation** (finance risk management). The observed hourly
   increments have excess kurtosis in the hundreds and strong positive skew
   (rain and irrigation arrive as jumps, drying is slow), so a Gaussian is the
   wrong law for the barrier problem. `crossing_probability_empirical` replaces
   it with the empirical increment distribution, the same move as pricing risk
   off the historical return distribution rather than a fitted normal.

2. **Optimal stopping** (American-option pricing, and the control-theory
   literature on event-triggered control). Irrigating is an exercise decision:
   pay a known cost now, or wait and risk paying the larger stress cost if the
   state crosses the barrier. Backward induction over the empirical increment
   law returns the *exercise boundary*, the moisture level at which irrigating
   becomes optimal. That boundary sits strictly above the stress barrier by an
   early-exercise premium, which is the quantity the shipped fixed threshold of
   25.0 currently assumes without deriving.

3. **Cost-loss economic value** (Murphy 1977, Richardson 2000, standard in
   operational meteorology and essentially absent from the irrigation-ML
   literature). Scores an alert rule by the expense a grower actually incurs
   across the range of cost-to-loss ratios, relative to the best trivial
   strategy. Accuracy metrics cannot see that an alert firing on 99 percent of
   hours is worthless; this one can.

Pure functions, no I/O. Every estimate is taken from a caller-supplied history,
so causality is the caller's contract; the walk-forward runner is
`scripts/d2_stopping.py`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation.first_passage import (
    SIGMA_FLOOR,
    ewma_drift_series,
    ewma_volatility_series,
    hourly_deltas,
)

# Increment distributions are discretized to this many equal-probability
# points for the dynamic program. Deterministic (quantiles, not sampling), so
# a run is reproducible without a seed.
N_INCREMENT_POINTS = 256

# Moisture grid step, in increment standard deviations. The grid has to resolve
# a typical one-hour move, so the step is a fraction of it; both the crossing
# probability and the boundary location converge as this shrinks.
GRID_STEP_SIGMAS = 0.1

# Guardrails on the derived node count, so a pathological scale cannot produce
# a 3-node or a 10-million-node grid.
MIN_GRID = 200
MAX_GRID = 6000

# Below this many gap-free pairs an increment pool is not trustworthy.
MIN_POOL = 48


def increment_pool(series: pd.Series) -> np.ndarray:
    """Gap-free hourly increments of `series` as a float array.

    Thin wrapper over `first_passage.hourly_deltas` so this module's callers
    never rebuild the gap-aware pairing rule. Gaps are excluded, never bridged.

    Args:
        series: hourly soil-moisture series, NaN at gap hours.

    Returns:
        The valid hourly changes, order preserved.
    """
    return hourly_deltas(series).to_numpy(dtype=float)


def standardized_pool(
    series: pd.Series,
    sigma_halflife: float = 72.0,
    mu_halflife: float = 336.0,
    min_pairs: int = 24,
) -> np.ndarray:
    """Increments divided by the conditional scale that applied when they happened.

    Raw pooled increments mix two regimes: quiet drydown, where the hourly move
    is a couple of hundredths, and storm or irrigation hours, where it is whole
    units. Pooling them produces a distribution whose width is set by the rare
    events and which cannot respond to the current regime at all. On these
    probes the unconditional pool standard deviation runs an order of magnitude
    above the causal EWMA volatility, so a barrier priced off the raw pool is
    answering a different question from the one `first_passage` asks.

    Filtered historical simulation (Barone-Adesi, Giannopoulos & Vosper 1999)
    is the standard repair in market-risk work: divide each historical move by
    the volatility estimate that was current when it occurred, keep the
    resulting standardized shape, and rescale it by today's volatility. What
    survives is the part of the distribution that is genuinely about shape,
    heavy tails and the upward skew of rain arrivals, with the regime taken out.

    Estimates are the causal EWMA series from `first_passage`, so each increment
    is standardized by information available strictly before it.

    Args:
        series: hourly soil-moisture series, NaN at gap hours.
        sigma_halflife: EWMA halflife for volatility, in pairs.
        mu_halflife: EWMA halflife for drift, in pairs.
        min_pairs: warmup before an estimate is trusted.

    Returns:
        Standardized increments, zero mean and roughly unit scale by
        construction. Empty if the series is too short.
    """
    deltas = hourly_deltas(series)
    if len(deltas) < min_pairs:
        return np.empty(0, dtype=float)
    sigma = ewma_volatility_series(series, halflife=sigma_halflife, min_pairs=min_pairs).reindex(
        deltas.index
    )
    mu = ewma_drift_series(series, halflife=mu_halflife, min_pairs=min_pairs).reindex(deltas.index)
    z = (deltas - mu) / sigma.where(sigma > SIGMA_FLOOR)
    return z.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)


def filtered_increments(
    z_pool: np.ndarray,
    mu: float,
    sigma: float,
    n_points: int = N_INCREMENT_POINTS,
) -> np.ndarray:
    """Rescale a standardized pool to the current conditional moments.

    The second half of filtered historical simulation: take the shape estimated
    over all history and stretch it to today's drift and volatility. The result
    is directly comparable to `gaussian_increments(mu, sigma)`, which has the
    same first two moments and differs only in shape, so a head-to-head run
    isolates what the heavy tails and the skew are worth.

    Args:
        z_pool: standardized increments (see `standardized_pool`).
        mu: current per-hour drift.
        sigma: current per-hour volatility, > 0.
        n_points: number of equal-probability points.

    Returns:
        Sorted increments of length `n_points`; empty if inputs are unusable.
    """
    if len(z_pool) < MIN_POOL or not np.isfinite(sigma) or sigma <= 0:
        return np.empty(0, dtype=float)
    if not np.isfinite(mu):
        return np.empty(0, dtype=float)
    probs = (np.arange(n_points) + 0.5) / n_points
    z = np.quantile(z_pool, probs)
    # Re-standardize the quantile set itself, so the returned law has exactly
    # the requested moments no matter how the tails were sampled.
    z = (z - z.mean()) / max(float(z.std()), 1e-12)
    return mu + sigma * z


def discretize_increments(
    pool: np.ndarray, n_points: int = N_INCREMENT_POINTS, drift: float | None = None
) -> np.ndarray:
    """Equal-probability discretization of an empirical increment distribution.

    Returns `n_points` quantiles of `pool` at the midpoints of equal-probability
    bins, which is a deterministic stand-in for sampling: averaging a function
    over these points approximates its expectation under the empirical law.

    Optionally re-centers the distribution on `drift`, which keeps the empirical
    shape (skew and fat tails) while imposing the locally estimated drying rate.
    The pool's own mean is a long-run average and understates how fast a probe
    is drying right now; the caller supplies the causal EWMA drift instead.

    Args:
        pool: empirical hourly increments.
        n_points: number of equal-probability points.
        drift: if given, the returned points are shifted to have this mean.

    Returns:
        Sorted increments of length `n_points`; empty if the pool is too small.
    """
    if len(pool) < MIN_POOL:
        return np.empty(0, dtype=float)
    probs = (np.arange(n_points) + 0.5) / n_points
    points = np.quantile(pool, probs)
    if drift is not None:
        points = points - points.mean() + drift
    return points


def gaussian_increments(mu: float, sigma: float, n_points: int = N_INCREMENT_POINTS) -> np.ndarray:
    """Equal-probability discretization of a Normal(mu, sigma) increment law.

    The ablation control. Feeding this to `crossing_curve` instead of the
    empirical pool holds the monitoring frequency fixed at hourly and changes
    only the distribution, which separates the two corrections the empirical
    curve makes to the Gaussian closed form: discrete monitoring, and the shape
    of the increment law.

    Args:
        mu: per-hour drift.
        sigma: per-hour volatility, > 0.
        n_points: number of equal-probability points.

    Returns:
        Sorted increments of length `n_points`; empty if sigma is unusable.
    """
    if not np.isfinite(sigma) or sigma <= 0 or not np.isfinite(mu):
        return np.empty(0, dtype=float)
    probs = (np.arange(n_points) + 0.5) / n_points
    # Inverse normal CDF by bisection on erfc, so scipy stays out of the deps.
    z = np.array([_ndtri(p) for p in probs])
    return mu + sigma * z


def _ndtri(p: float) -> float:
    """Standard-normal quantile via bisection on the CDF. No scipy."""
    from math import erfc, sqrt

    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if 0.5 * erfc(-mid / sqrt(2.0)) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def crossing_curve(
    increments: np.ndarray, threshold: float, horizon_h: int
) -> tuple[np.ndarray, np.ndarray]:
    """Crossing probability as a function of starting level, for one horizon.

    The empirical-law counterpart of `first_passage.crossing_probability`, and
    the quantity that formula gets wrong twice over: it prices a *continuously*
    monitored barrier under a *Gaussian* law, while the alert label is scored on
    hourly readings under an increment distribution with heavy tails and strong
    positive skew. Both corrections push in the same direction, and the
    continuous-monitoring bias is the larger of the two at short horizons.

    Writing u_k(S) for the probability of surviving k more hours from level S,

        u_0(S) = 1                                    for S > threshold
        u_k(S) = E_d[ u_{k-1}(S + d) * 1{S + d > threshold} ]

    which is one backward recursion over the whole grid, so every starting level
    is priced by the same pass rather than one dynamic program per row.

    Args:
        increments: discretized increment law (see `discretize_increments`).
        threshold: barrier level.
        horizon_h: window length in hours, > 0.

    Returns:
        `(grid, probs)`, the level grid and 1 - u_h on it. Both empty if the
        increment law is unusable.
    """
    if len(increments) == 0 or horizon_h <= 0:
        return np.empty(0), np.empty(0)
    mean, sd = float(increments.mean()), float(increments.std())
    span = abs(mean) * horizon_h + 8.0 * sd * np.sqrt(horizon_h)
    grid = _level_grid(threshold, span, increments)
    survive = np.ones(len(grid))
    dest = grid[:, None] + increments[None, :]
    alive = dest > threshold
    for _ in range(horizon_h):
        # Mass above the top node is treated as surviving, which is safe because
        # the grid reaches eight horizon spreads above the barrier.
        nxt = np.interp(dest, grid, survive)
        survive = np.where(alive, nxt, 0.0).mean(axis=1)
    return grid, np.clip(1.0 - survive, 0.0, 1.0)


def crossing_probability_empirical(
    levels: np.ndarray | float,
    threshold: float,
    horizon_h: int,
    increments: np.ndarray,
) -> np.ndarray:
    """P(an hourly reading falls to or below `threshold` within (t, t+h]).

    Vectorized over `levels`: the backward recursion runs once and every level
    is read off the resulting curve. Levels already at or below the barrier get
    probability 1.

    Args:
        levels: starting soil-moisture level(s) at decision time.
        threshold: barrier level.
        horizon_h: window length in hours, > 0.
        increments: discretized increment law (see `discretize_increments`).

    Returns:
        Probabilities in [0, 1], same shape as `levels`; NaN where unusable.
    """
    arr = np.atleast_1d(np.asarray(levels, dtype=float))
    grid, probs = crossing_curve(increments, threshold, horizon_h)
    if len(grid) == 0:
        return np.full(arr.shape, np.nan)
    out = np.interp(arr, grid, probs)
    out = np.where(arr <= threshold, 1.0, out)
    return np.where(np.isfinite(arr), out, np.nan)


def _level_grid(lo: float, span: float, increments: np.ndarray) -> np.ndarray:
    """Uniform level grid from `lo` upward, resolved to the increment scale."""
    step = max(float(increments.std()) * GRID_STEP_SIGMAS, 1e-9)
    n = int(np.clip(round(span / step) + 1, MIN_GRID, MAX_GRID))
    return np.linspace(lo, lo + max(span, 1e-6), n)


def exercise_boundary(
    increments: np.ndarray,
    threshold: float,
    horizon_h: int,
    cost_ratio: float,
    grid_hi: float,
) -> np.ndarray:
    """Optimal irrigation trigger level by hours remaining, via backward induction.

    The decision problem, in units of the stress loss (so the loss is 1 and the
    irrigation cost is `cost_ratio`): at each hour, either irrigate now for a
    certain `cost_ratio`, or wait one hour and face the same decision with one
    less hour of protection. Falling to or below `threshold` before irrigating
    costs the full 1 and ends the episode.

    Writing V_k for the cost-to-go with k hours of exposure remaining,

        V_0(S) = 0                       for S > threshold
        V_k(S) = min(cost_ratio, E_d[V_{k-1}(S + d)])
        V_k(S) = 1                       for S <= threshold, any k

    the continuation value is decreasing in S, so the irrigate region is the
    interval below a single boundary, returned per k. The boundary lies strictly
    above `threshold` whenever `cost_ratio` < 1: that gap is the early-exercise
    premium, the amount of headroom worth buying because stress cannot be undone
    after the fact.

    Args:
        increments: discretized increment law (see `discretize_increments`).
        threshold: stress barrier.
        horizon_h: longest exposure window considered, in hours.
        cost_ratio: irrigation cost divided by stress loss, in (0, 1).
        grid_hi: top of the moisture grid; should sit well above the barrier.

    Returns:
        Array of length `horizon_h`; entry k-1 is the trigger level with k hours
        remaining. Equal to `threshold` where waiting is always optimal.
    """
    if len(increments) == 0 or not 0.0 < cost_ratio < 1.0:
        return np.full(horizon_h, np.nan)
    grid = _level_grid(threshold, max(grid_hi - threshold, 1e-6), increments)
    value = np.zeros(len(grid))
    boundaries = np.empty(horizon_h)
    for k in range(horizon_h):
        cont = _continuation(grid, value, increments, threshold)
        boundaries[k] = _boundary_level(grid, cont, cost_ratio, threshold)
        value = np.minimum(cont, cost_ratio)
    return boundaries


def _continuation(
    grid: np.ndarray, value: np.ndarray, increments: np.ndarray, threshold: float
) -> np.ndarray:
    """E[V(S + d)] at every grid level, with the barrier absorbing at cost 1."""
    dest = grid[:, None] + increments[None, :]
    vals = np.interp(dest, grid, value)
    vals = np.where(dest <= threshold, 1.0, vals)
    return vals.mean(axis=1)


def _boundary_level(
    grid: np.ndarray, cont: np.ndarray, cost_ratio: float, threshold: float
) -> float:
    """Highest level at which irrigating (cost_ratio) beats waiting (cont)."""
    irrigate = cont >= cost_ratio
    if not irrigate.any():
        return float(threshold)
    top = int(np.max(np.flatnonzero(irrigate)))
    if top == len(grid) - 1:
        return float(grid[-1])
    # Linear crossing between the last irrigate node and the first wait node.
    c0, c1 = cont[top], cont[top + 1]
    if c0 == c1:
        return float(grid[top])
    w = (c0 - cost_ratio) / (c0 - c1)
    return float(grid[top] + w * (grid[top + 1] - grid[top]))


def exercise_boundary_delayed(
    increments: np.ndarray,
    threshold: float,
    horizon_h: int,
    cost_ratio: float,
    delay_h: int,
    grid_hi: float,
) -> np.ndarray:
    """Optimal irrigation trigger when water lands `delay_h` hours after the order.

    Same decision problem as `exercise_boundary`, with one operational change:
    protection is no longer instant. Ordering water starts a crew and valve
    rotation that takes `delay_h` hours, and the level keeps walking while it
    runs, so paying the cost still leaves min(delay_h, k) hours of crossing
    exposure. Writing Q_j(S) for the probability that the walk from S falls to
    or below `threshold` within j hourly steps (Q_0 = 0),

        X_k(S) = cost_ratio + Q_{min(delay_h, k)}(S)     exercise value
        W_k(S) = E_d[V_{k-1}(S + d)]                     continuation value
        V_0(S) = 0                    for S > threshold
        V_k(S) = min(X_k(S), W_k(S))
        V_k(S) = 1                    for S <= threshold, any k

    Both X_k and W_k decrease in S, so the irrigate region is again the
    interval below a single boundary, the highest S with X_k(S) <= W_k(S).
    With `delay_h` = 0 the exercise value is the constant `cost_ratio` and the
    recursion reduces exactly to `exercise_boundary`. With k <= `delay_h` the
    water cannot land inside the exposure window, irrigating buys nothing over
    waiting, and the boundary sits at `threshold`; for k > `delay_h` the delay
    pushes the trigger up, which prices the operational cost of a slow
    response. Q_j is evaluated once per j in 1 to min(delay_h, horizon_h) via
    `crossing_curve` and interpolated onto the boundary grid.

    Args:
        increments: discretized increment law (see `discretize_increments`).
        threshold: stress barrier.
        horizon_h: longest exposure window considered, in hours.
        cost_ratio: irrigation cost divided by stress loss, in (0, 1).
        delay_h: hours from ordering irrigation to the water landing, >= 0.
        grid_hi: top of the moisture grid; should sit well above the barrier.

    Returns:
        Array of length `horizon_h`; entry k-1 is the trigger level with k hours
        remaining. Equal to `threshold` where irrigating is never optimal.
    """
    if len(increments) == 0 or not 0.0 < cost_ratio < 1.0 or delay_h < 0:
        return np.full(horizon_h, np.nan)
    grid = _level_grid(threshold, max(grid_hi - threshold, 1e-6), increments)
    # Q_j on the boundary grid, one curve per exposure length the delay creates.
    q_curves = [np.zeros(len(grid))]
    for j in range(1, min(delay_h, horizon_h) + 1):
        c_grid, c_probs = crossing_curve(increments, threshold, j)
        q_curves.append(np.where(grid <= threshold, 1.0, np.interp(grid, c_grid, c_probs)))
    value = np.zeros(len(grid))
    boundaries = np.empty(horizon_h)
    for k in range(1, horizon_h + 1):
        cont = _continuation(grid, value, increments, threshold)
        exercise = cost_ratio + q_curves[min(delay_h, k)]
        boundaries[k - 1] = _boundary_level_two_curves(grid, cont, exercise, threshold)
        value = np.minimum(cont, exercise)
    return boundaries


def _boundary_level_two_curves(
    grid: np.ndarray, cont: np.ndarray, exercise: np.ndarray, threshold: float
) -> float:
    """Highest level at which exercising beats waiting, for a level-dependent cost.

    The same last-node plus linear-interpolation rule as `_boundary_level`,
    applied to the gap W - X so it also covers an exercise value that varies
    with the level.
    """
    gap = cont - exercise
    irrigate = gap >= 0.0
    if not irrigate.any():
        return float(threshold)
    top = int(np.max(np.flatnonzero(irrigate)))
    if top == len(grid) - 1:
        return float(grid[-1])
    g0, g1 = gap[top], gap[top + 1]
    if g0 == g1:
        return float(grid[top])
    w = g0 / (g0 - g1)
    return float(grid[top] + w * (grid[top + 1] - grid[top]))


def distance_to_threshold(level: float, threshold: float, sigma: float, horizon_h: int) -> float:
    """Headroom to the barrier measured in horizon volatilities.

    The soil-moisture analogue of Merton's distance to default: a scale-free
    number that is comparable across probes whose ranges and noise differ. A
    value of 2 means the barrier is two horizon-standard-deviations away.

    Args:
        level: last observed soil moisture.
        threshold: barrier level.
        sigma: per-hour volatility.
        horizon_h: window length in hours.

    Returns:
        (level - threshold) / (sigma * sqrt(horizon_h)); NaN if sigma is 0.
    """
    if not np.isfinite(sigma) or sigma <= 0 or horizon_h <= 0:
        return float("nan")
    return float((level - threshold) / (sigma * np.sqrt(horizon_h)))


def cost_loss_expense(alert: np.ndarray, event: np.ndarray, alpha: float) -> float:
    """Mean expense per decision, in units of the stress loss.

    The standard cost-loss contingency model: acting costs `alpha` whether or
    not the event follows; not acting costs 1 when the event occurs and 0
    otherwise.

    Args:
        alert: boolean protective-action decisions.
        event: boolean realized outcomes.
        alpha: cost-to-loss ratio in (0, 1).

    Returns:
        Mean expense; NaN on empty input.
    """
    if len(alert) == 0:
        return float("nan")
    a = np.asarray(alert, dtype=bool)
    e = np.asarray(event, dtype=bool)
    return float(np.mean(np.where(a, alpha, np.where(e, 1.0, 0.0))))


def economic_value(alert: np.ndarray, event: np.ndarray, alpha: float) -> float:
    """Value of an alert rule relative to the better trivial strategy.

    V = (E_climate - E_forecast) / (E_climate - E_perfect), where E_climate is
    the cheaper of always acting and never acting, and E_perfect acts exactly on
    the event hours. V = 1 is a perfect rule, V <= 0 is a rule no better than
    doing the same thing every hour. This is the number that exposes a trigger
    which fires on almost every hour: it can be accurate and still worthless.

    Args:
        alert: boolean protective-action decisions.
        event: boolean realized outcomes.
        alpha: cost-to-loss ratio in (0, 1).

    Returns:
        Economic value; NaN when the reference strategies coincide.
    """
    if len(alert) == 0:
        return float("nan")
    e = np.asarray(event, dtype=bool)
    s = float(e.mean())
    e_climate = min(alpha, s)
    e_perfect = alpha * s
    denom = e_climate - e_perfect
    if abs(denom) < 1e-12:
        return float("nan")
    return float((e_climate - cost_loss_expense(alert, e, alpha)) / denom)
