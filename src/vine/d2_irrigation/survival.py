"""Time-to-event layer for the irrigation clock (D2).

Every layer so far answers a fixed-horizon question: what will the level be at
t+h, or will it cross the barrier within h hours. The question a grower asks is
the transpose: *how long until this block needs water?* That is a time-to-event
problem, and the discipline that owns it is survival analysis, standard in
medical statistics and essentially absent from irrigation forecasting, where
the practice tool is a deterministic drydown calculator (current rate, divide,
done).

The import matters for a second reason: censoring. The stopping layer scores a
window only when all h future readings exist, so every decision cut short by a
sensor gap or the end of the record is silently dropped, and dropping them
conditions on the future. Survival analysis keeps those rows as right-censored
observations and reweights the scored ones (inverse probability of censoring
weighting, Graf et al. 1999), so the evaluation uses every decision hour.

Pieces, all pure and I/O-free:

- `survival_labels` — first crossing time of a drawdown barrier, right-censored
  at the first missing reading or the end of the record.
- `kaplan_meier` / `censoring_survival` — the classical product-limit curves
  for the event and for the censoring process.
- `censored_brier_curve` / `integrated_brier` — IPCW Brier score per horizon
  and its integral, the proper score for a predicted survival curve.
- `survival_curve_grid` — one backward recursion that prices survival for
  every horizon 1..H and every starting level at once, for any discretized
  increment law (Gaussian or filtered historical simulation).
- `person_periods` / `hazard_design` / `fit_hazard` / `hazard_survival` — a
  discrete-time hazard regression (Singer & Willett 1993): expand each
  decision into at-risk hourly periods, fit a pooled logistic hazard on
  causal covariates (baseline-hazard shape, hour of day at the target hour,
  standardized drift, depth, volatility), and compose predicted hazards into
  a survival curve. Censoring is handled by the likelihood itself: censored
  rows simply contribute fewer at-risk periods.
- `clock_survival` — the deterministic drydown calculator as a degenerate
  survival curve, so current practice is scored on the same metric.
- `quantile_times` — turn a survival curve into the operator-facing reading:
  median hours to trigger and an interval around it.

The walk-forward runner is `scripts/d2_survival.py`.
"""

from __future__ import annotations

import numpy as np

from vine.d2_irrigation.stopping import _level_grid


def survival_labels(
    values: np.ndarray, drop: float, max_h: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """First-crossing times of a moving drawdown barrier, right-censored.

    For each decision index i with an observed reading, scan the next `max_h`
    hours in order. The event is the first observed reading at or below
    `values[i] - drop`. Observation stops at the first missing reading: a
    crossing seen only after a gap cannot be timed, so the row is censored at
    the last gap-free hour. A row observed through all `max_h` hours with no
    crossing is recorded with time `max_h + 1`, meaning it is known to survive
    the whole evaluation window.

    Args:
        values: hourly soil-moisture readings, NaN at gap hours.
        drop: drawdown depth defining the event, > 0.
        max_h: evaluation window in hours, > 0.

    Returns:
        `(idx, time, event)`: decision indices, hours to event or censoring
        (1..max_h, or max_h + 1 for full survival), and the event indicator.
        Rows with a missing decision reading or zero observed hours are
        excluded.
    """
    if drop <= 0 or max_h <= 0:
        raise ValueError("drop and max_h must be positive")
    n = len(values)
    obs = np.isfinite(values)
    padded = np.concatenate([values, np.full(max_h, np.nan)])
    fut = np.lib.stride_tricks.sliding_window_view(padded[1:], max_h)[:n]
    obs_f = np.isfinite(fut)
    gap_any = (~obs_f).any(axis=1)
    first_gap = np.where(gap_any, (~obs_f).argmax(axis=1), max_h)
    hour = np.arange(max_h)[None, :]
    crossed = obs_f & (fut <= values[:, None] - drop) & (hour < first_gap[:, None])
    event = crossed.any(axis=1)
    first_cross = crossed.argmax(axis=1) + 1
    time = np.where(event, first_cross, np.where(first_gap == max_h, max_h + 1, first_gap))
    keep = obs & (time >= 1)
    return np.flatnonzero(keep), time[keep].astype(int), event[keep]


def kaplan_meier(time: np.ndarray, event: np.ndarray, max_h: int) -> np.ndarray:
    """Product-limit survival curve S(h) = P(T > h) on the hourly grid.

    At each hour j, the at-risk set is everyone whose recorded time is >= j
    (censored rows were still under observation at their censoring hour), and
    the factor is 1 - d_j / n_j with d_j the events recorded at j.

    Args:
        time: hours to event or censoring, >= 1.
        event: True where the recorded time is an event.
        max_h: grid length in hours.

    Returns:
        Array of length `max_h`; entry h-1 is S(h). All ones on empty input.
    """
    t = np.asarray(time)
    e = np.asarray(event, dtype=bool)
    surv = np.ones(max_h)
    s = 1.0
    for j in range(1, max_h + 1):
        n_j = int((t >= j).sum())
        d_j = int(((t == j) & e).sum())
        if n_j > 0:
            s *= 1.0 - d_j / n_j
        surv[j - 1] = s
    return surv


def censoring_survival(time: np.ndarray, event: np.ndarray, max_h: int) -> np.ndarray:
    """Reverse Kaplan-Meier: G(h) = P(censoring time > h), for IPCW weights.

    The same product-limit estimator with the roles swapped: censorings are
    the events. Rows with time `max_h + 1` (observed through the full window)
    never count as censored inside the grid.

    Args:
        time: hours to event or censoring, >= 1.
        event: True where the recorded time is an event.
        max_h: grid length in hours.

    Returns:
        Array of length `max_h + 1`; entry j is G(j), with G(0) = 1.
    """
    t = np.asarray(time)
    e = np.asarray(event, dtype=bool)
    g = np.ones(max_h + 1)
    s = 1.0
    for j in range(1, max_h + 1):
        n_j = int((t >= j).sum())
        c_j = int(((t == j) & ~e).sum())
        if n_j > 0:
            s *= 1.0 - c_j / n_j
        g[j] = s
    return g


def censored_brier_curve(
    time: np.ndarray,
    event: np.ndarray,
    surv: np.ndarray,
    g: np.ndarray,
) -> np.ndarray:
    """IPCW Brier score of predicted survival curves, per horizon (Graf 1999).

    At horizon h, a row scored as an event by h contributes S_i(h)^2 weighted
    by 1/G(T_i - 1); a row known to survive past h contributes (1 - S_i(h))^2
    weighted by 1/G(h); a row censored at or before h without an event gets
    weight zero. The divisor is the full row count, so dropped information is
    paid for by the weights, not hidden.

    Args:
        time: hours to event or censoring, >= 1.
        event: True where the recorded time is an event.
        surv: predicted survival, shape (n_rows, max_h); column h-1 is S(h).
        g: censoring survival from `censoring_survival`, length max_h + 1.

    Returns:
        Brier score per horizon, length max_h. NaN on empty input.
    """
    t = np.asarray(time)
    e = np.asarray(event, dtype=bool)
    n, max_h = surv.shape
    if n == 0:
        return np.full(max_h, np.nan)
    g = np.maximum(np.asarray(g, dtype=float), 1e-6)
    out = np.empty(max_h)
    w_event = np.where(e, 1.0 / g[np.minimum(t - 1, max_h)], 0.0)
    for h in range(1, max_h + 1):
        s_h = surv[:, h - 1]
        died = e & (t <= h)
        alive = t > h
        contrib = np.where(died, w_event * s_h**2, 0.0)
        contrib += np.where(alive, (1.0 - s_h) ** 2 / g[h], 0.0)
        out[h - 1] = float(contrib.sum() / n)
    return out


def integrated_brier(bs_curve: np.ndarray) -> float:
    """Integrated Brier score: the mean over the uniform hourly grid."""
    if len(bs_curve) == 0:
        return float("nan")
    return float(np.mean(bs_curve))


def survival_curve_grid(increments: np.ndarray, max_h: int) -> tuple[np.ndarray, np.ndarray]:
    """Survival probability for every horizon and starting level, barrier at 0.

    The all-horizons counterpart of `stopping.crossing_curve`: the same
    backward recursion, but the survival vector is recorded after every step,
    so one pass prices the whole curve 1..max_h. Starting levels are read in
    barrier units (level minus barrier); callers standardize by sigma so one
    curve serves every row sharing a drift bucket.

    Args:
        increments: discretized increment law (see `stopping.discretize_increments`).
        max_h: longest horizon in hours, > 0.

    Returns:
        `(grid, surv)` with `surv[k - 1, :]` the probability of surviving k
        hours from each grid level. Both empty if the law is unusable.
    """
    if len(increments) == 0 or max_h <= 0:
        return np.empty(0), np.empty((0, 0))
    mean, sd = float(increments.mean()), float(increments.std())
    span = abs(mean) * max_h + 8.0 * sd * np.sqrt(max_h)
    grid = _level_grid(0.0, span, increments)
    survive = np.ones(len(grid))
    dest = grid[:, None] + increments[None, :]
    alive = dest > 0.0
    out = np.empty((max_h, len(grid)))
    for k in range(max_h):
        nxt = np.interp(dest, grid, survive)
        survive = np.where(alive, nxt, 0.0).mean(axis=1)
        out[k] = survive
    return grid, np.clip(out, 0.0, 1.0)


PERIOD_BUCKETS = ((1, 3), (4, 6), (7, 12), (13, 24), (25, 48))


def person_periods(
    time: np.ndarray, event: np.ndarray, max_h: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Expand survival labels into at-risk (row, hour) pairs for hazard fitting.

    A row observed through hour t contributes one binary outcome per hour
    1..min(t, max_h): zero while it survives, one at its event hour. Censored
    rows simply stop contributing at their censoring hour, which is exactly
    how the discrete-time likelihood absorbs censoring; no reweighting is
    needed at fit time.

    Args:
        time: hours to event or censoring, >= 1 (max_h + 1 = survived window).
        event: True where the recorded time is an event.
        max_h: evaluation window in hours.

    Returns:
        `(rows, period, died)`: index into the input labels, the at-risk hour
        (1-based), and the binary event outcome for that hour.
    """
    t = np.asarray(time)
    e = np.asarray(event, dtype=bool)
    if len(t) == 0:
        return np.empty(0, dtype=int), np.empty(0, dtype=int), np.empty(0)
    stop = np.minimum(t, max_h)
    rows = np.repeat(np.arange(len(t)), stop)
    period = np.concatenate([np.arange(1, s + 1) for s in stop])
    died = (period == t[rows]) & e[rows]
    return rows, period, died.astype(float)


def hazard_design(period: np.ndarray, hod: np.ndarray, m: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Feature matrix for the pooled logistic hazard, one row per person-period.

    Columns: piecewise baseline-hazard dummies over `PERIOD_BUCKETS` (how far
    into the window the at-risk hour is), sine and cosine of the hour of day
    at that target hour (the diurnal evapotranspiration phase, which no
    random-walk model can see), the standardized drift m = mu / sigma, and
    log depth log(x) with x = drop / sigma. All causal at decision time.

    Args:
        period: at-risk hour within the window, 1-based.
        hod: hour of day (0..23) at the target hour, decision hour + period.
        m: standardized drift of the decision row.
        x: standardized barrier depth of the decision row, > 0.

    Returns:
        Array of shape (n, 9).
    """
    cols = [((period >= lo) & (period <= hi)).astype(float) for lo, hi in PERIOD_BUCKETS]
    phase = 2.0 * np.pi * np.asarray(hod, dtype=float) / 24.0
    cols += [np.sin(phase), np.cos(phase), np.asarray(m, dtype=float), np.log(x)]
    return np.column_stack(cols)


def fit_hazard(X: np.ndarray, died: np.ndarray):
    """Fit the pooled logistic hazard (Singer & Willett 1993).

    A discrete-time survival model: the likelihood of person-period outcomes
    under an hour-level hazard is exactly a logistic regression on the
    expanded rows. L2-regularized, deterministic (lbfgs), standardized
    features.

    Args:
        X: design matrix from `hazard_design`.
        died: binary outcomes from `person_periods`.

    Returns:
        A fitted sklearn pipeline, or None when the outcomes are degenerate
        (no events, or nothing but events).
    """
    if len(died) == 0 or died.sum() == 0 or died.sum() == len(died):
        return None
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X, died)


def hazard_survival(
    model, hod0: np.ndarray, m: np.ndarray, x: np.ndarray, max_h: int
) -> np.ndarray:
    """Survival curves from a fitted hazard model, S(h) = prod(1 - lambda_j).

    Args:
        model: fitted pipeline from `fit_hazard` (None gives NaN curves).
        hod0: hour of day (0..23) at each decision time.
        m: standardized drift per decision row.
        x: standardized barrier depth per decision row, > 0.
        max_h: evaluation window in hours.

    Returns:
        Array of shape (n, max_h); column h-1 is S(h).
    """
    n = len(m)
    if model is None or n == 0:
        return np.full((n, max_h), np.nan)
    period = np.tile(np.arange(1, max_h + 1), n)
    rep = np.repeat(np.arange(n), max_h)
    hod = (np.asarray(hod0)[rep] + period) % 24
    lam = model.predict_proba(hazard_design(period, hod, m[rep], x[rep]))[:, 1]
    return np.cumprod(1.0 - lam.reshape(n, max_h), axis=1)


def clock_survival(mu: float, drop: float, max_h: int) -> np.ndarray:
    """The deterministic drydown calculator as a survival curve.

    Current practice: divide the remaining depletion by the current drying
    rate. The implied survival curve is a step function at drop / (-mu); a
    non-drying rate predicts no crossing inside the window at all. Scored on
    the same IPCW Brier as the probabilistic models, this is the baseline that
    represents what growers use today.

    Args:
        mu: current per-hour drift (negative while drying).
        drop: drawdown depth defining the event, > 0.
        max_h: grid length in hours.

    Returns:
        Array of length `max_h`; entry h-1 is the predicted P(T > h), 0 or 1.
        NaN everywhere if `mu` is not finite.
    """
    if not np.isfinite(mu):
        return np.full(max_h, np.nan)
    hours = np.arange(1, max_h + 1, dtype=float)
    if mu >= 0:
        return np.ones(max_h)
    return (hours < drop / (-mu)).astype(float)


def quantile_times(surv_row: np.ndarray, qs: tuple[float, ...]) -> list[float]:
    """Hours at which the crossing probability first reaches each quantile.

    The operator-facing reading: q = 0.5 is the median time to trigger. A
    quantile the curve never reaches inside the window is reported as inf,
    read as "beyond the evaluation window".

    Args:
        surv_row: one survival curve, entry h-1 = S(h).
        qs: crossing-probability levels in (0, 1).

    Returns:
        One time (in hours) per quantile, inf where not reached.
    """
    cross = 1.0 - np.asarray(surv_row, dtype=float)
    out = []
    for q in qs:
        hit = np.flatnonzero(cross >= q)
        out.append(float(hit[0] + 1) if len(hit) else float("inf"))
    return out
