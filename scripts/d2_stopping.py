"""Walk-forward evaluation of the optimal-stopping decision layer (D2).

Three questions, run over the same purged expanding folds as every other D2
experiment, on all five soil probes at 6/12/24/48 h.

**1. Is the Gaussian first-passage layer pricing the right barrier?** The
shipped analysis uses a continuous-monitoring reflection-principle formula
under a Normal increment law, but the alert label is scored on *hourly*
readings, and the observed increments are far from Normal. Two corrections are
evaluated separately so their contributions can be told apart:

    gauss_continuous   incumbent: continuous monitoring, Gaussian     (baseline)
    gauss_discrete     hourly monitoring, Gaussian                    (isolates monitoring)
    filtered_empirical hourly monitoring, filtered historical shape   (adds distribution)

**2. What should the trigger level be?** The shipped rule fires below a fixed
25.0. Backward induction over the increment law returns the level at which
irrigating beats waiting, given a cost-to-loss ratio, so the trigger is derived
rather than assumed.

**3. Is the shipped rule worth anything to a grower?** Brier and log loss
cannot see that a trigger firing on 99 percent of hours is useless. Cost-loss
economic value can, and it is reported across the ratio grid.

    uv run python scripts/d2_stopping.py
    uv run python scripts/d2_stopping.py configs/d2_irrigation/stopping.yaml --no-mlflow

Everything is computed in units of the conditional volatility, where the
crossing problem depends only on the standardized drift and the horizon, so one
backward recursion serves a whole bucket of rows. Writes deterministic CSVs to
docs/reports/assets/ and logs to MLflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel

from vine.common.config import load_config
from vine.common.seed import seed_everything
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.first_passage import (
    crossing_probability,
    ewma_drift_series,
    ewma_volatility_series,
)
from vine.d2_irrigation.stopping import (
    crossing_curve,
    economic_value,
    exercise_boundary,
    exercise_boundary_delayed,
    gaussian_increments,
    standardized_pool,
)
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice

ASSETS = Path("docs/reports/assets")
PROB_MODELS = (
    "gauss_continuous",
    "gauss_discrete",
    "filtered_empirical",
    "persistence_alert",
    "base_rate",
)
EPS = 1e-15  # log-loss clip, sklearn's default


class StoppingConfig(BaseModel):
    threshold: float = 25.0
    # "drawdown" asks whether the level falls `drawdown` below where it is now,
    # which is stationary and is what an allowable-depletion trigger means.
    # "fixed" reproduces the shipped absolute 25.0 rule. "quantile" calibrates
    # an absolute barrier per probe from first-fold training levels.
    barrier_mode: str = "drawdown"
    drawdown: float = 0.3
    barrier_quantile: float = 0.20
    horizons_h: list[int] = [6, 12, 24, 48]
    n_folds: int = 5
    sigma_halflife_h: float = 72.0
    mu_halflife_h: float = 336.0
    min_pairs: int = 24
    n_drift_buckets: int = 24
    cost_ratios: list[float] = [0.02, 0.05, 0.1, 0.2, 0.3, 0.5]
    delay_hours_h: list[int] = [0, 2, 4, 8, 12, 24]


def absolute_labels(obs: np.ndarray, below: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Per decision index i: (window fully observed, crossed within (i, i+h])."""
    n = len(obs)
    co = np.concatenate([[0], np.cumsum(obs)])
    cb = np.concatenate([[0], np.cumsum(below)])
    evaluable = np.zeros(n, dtype=bool)
    crossed = np.zeros(n, dtype=bool)
    idx = np.arange(n - h)
    evaluable[idx] = obs[idx] & (co[idx + 1 + h] - co[idx + 1] == h)
    crossed[idx] = (cb[idx + 1 + h] - cb[idx + 1]) > 0
    return evaluable, crossed


def drawdown_labels(
    values: np.ndarray, obs: np.ndarray, h: int, drop: float
) -> tuple[np.ndarray, np.ndarray]:
    """Per decision index i: (window observed, level fell `drop` below values[i]).

    The barrier travels with the state, so the event is a drawdown rather than
    an absolute level. That keeps the question well posed through a season-long
    drying trend, which an absolute barrier cannot: any fixed level is
    unreachable early in the record and already breached late in it.
    """
    n = len(values)
    co = np.concatenate([[0], np.cumsum(obs)])
    evaluable = np.zeros(n, dtype=bool)
    crossed = np.zeros(n, dtype=bool)
    idx = np.arange(n - h)
    evaluable[idx] = obs[idx] & (co[idx + 1 + h] - co[idx + 1] == h)
    # Minimum over the h readings strictly after each decision index.
    filled = np.where(obs, values, np.inf)
    windows = np.lib.stride_tricks.sliding_window_view(filled[1:], h)
    fmin = windows.min(axis=1)
    crossed[idx] = fmin[idx] <= values[idx] - drop
    return evaluable, crossed


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def unit_shape(z_pool: np.ndarray, n_points: int) -> np.ndarray:
    """Zero-mean unit-scale quantile shape of a standardized increment pool."""
    probs = (np.arange(n_points) + 0.5) / n_points
    z = np.quantile(z_pool, probs)
    return (z - z.mean()) / max(float(z.std()), 1e-12)


def standardized_curve(shape: np.ndarray, m: float, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Crossing curve in volatility units: barrier at 0, increments `m + shape`.

    Writing x = (level - barrier) / sigma and m = mu / sigma, a walk whose steps
    are `mu + sigma * shape` crosses the barrier exactly when the standardized
    walk with steps `m + shape` crosses zero. Both increment laws used here are
    of that form, so one curve per (shape, m, h) serves every row that shares a
    drift bucket, whatever its level and volatility.
    """
    return crossing_curve(m + shape, 0.0, h)


def bucket_drifts(m: np.ndarray, n_buckets: int) -> tuple[np.ndarray, np.ndarray]:
    """Assign standardized drifts to equal-count buckets; return (index, centers)."""
    finite = m[np.isfinite(m)]
    if len(finite) == 0:
        return np.zeros(len(m), dtype=int), np.array([0.0])
    edges = np.unique(np.quantile(finite, np.linspace(0, 1, n_buckets + 1)[1:-1]))
    idx = np.searchsorted(edges, m, side="right")
    centers = np.array(
        [
            np.median(finite[np.searchsorted(edges, finite, side="right") == b])
            for b in range(len(edges) + 1)
        ]
    )
    return idx, centers


def evaluate_device(
    y: pd.Series, cfg: StoppingConfig
) -> tuple[float, dict[int, dict[str, np.ndarray]]]:
    """Barrier plus, per horizon, the holdout labels and every probability forecast."""
    values = y.to_numpy(dtype=float)
    obs = np.isfinite(values)
    sigma = ewma_volatility_series(y, cfg.sigma_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    mu = ewma_drift_series(y, cfg.mu_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    splits = expanding_splits(len(y), cfg.n_folds)

    # One barrier for the whole holdout. Absolute modes fix a level from the
    # first fold's training slice so the event definition is causal and
    # identical across folds. Drawdown mode has no fixed level, the barrier
    # travels with the state, so the recorded value is the drop itself.
    if cfg.barrier_mode == "fixed":
        barrier = cfg.threshold
    elif cfg.barrier_mode == "quantile":
        barrier = float(np.nanquantile(values[: splits[0][0].stop], cfg.barrier_quantile))
    else:
        barrier = cfg.drawdown

    m_all = np.divide(mu, sigma, out=np.full_like(mu, np.nan), where=sigma > 0)
    if cfg.barrier_mode == "drawdown":
        below = np.zeros(len(values), dtype=bool)  # no absolute level to be below
        # Standardized headroom is constant in level terms: the walk starts
        # `drawdown` above the moving barrier at every decision time.
        x_all = np.divide(
            np.full_like(values, cfg.drawdown),
            sigma,
            out=np.full_like(values, np.nan),
            where=sigma > 0,
        )
    else:
        below = obs & (np.nan_to_num(values, nan=np.inf) <= barrier)
        x_all = np.divide(
            values - barrier, sigma, out=np.full_like(values, np.nan), where=sigma > 0
        )

    out: dict[int, dict[str, np.ndarray]] = {}
    for h in cfg.horizons_h:
        if cfg.barrier_mode == "drawdown":
            evaluable, crossed = drawdown_labels(values, obs, h, cfg.drawdown)
        else:
            evaluable, crossed = absolute_labels(obs, below, h)
        scorable = evaluable & np.isfinite(sigma) & np.isfinite(mu) & (sigma > 0)
        ys: list[float] = []
        idxs: list[int] = []
        preds: dict[str, list[float]] = {k: [] for k in PROB_MODELS}
        for tr, te in splits:
            purged = purged_train_slice(tr, h - 1)
            train_eval = evaluable[: purged.stop]
            rate = float(crossed[: purged.stop][train_eval].mean()) if train_eval.any() else 0.5
            # Increment shape from training rows only.
            z_pool = standardized_pool(
                y.iloc[: purged.stop], cfg.sigma_halflife_h, cfg.mu_halflife_h, cfg.min_pairs
            )
            shape = unit_shape(z_pool, 256) if len(z_pool) >= 48 else None
            rows = [i for i in range(te.start, te.stop) if scorable[i]]
            if not rows:
                continue
            ri = np.array(rows)
            bidx, centers = bucket_drifts(m_all[ri], cfg.n_drift_buckets)
            gauss_shape = gaussian_increments(0.0, 1.0, 256)
            curves: dict[tuple[str, int], tuple[np.ndarray, np.ndarray]] = {}
            for b, m_c in enumerate(centers):
                curves[("gauss_discrete", b)] = standardized_curve(gauss_shape, float(m_c), h)
                if shape is not None:
                    curves[("filtered_empirical", b)] = standardized_curve(shape, float(m_c), h)
            for k, i in enumerate(rows):
                ys.append(float(crossed[i]))
                idxs.append(i)
                if cfg.barrier_mode == "drawdown":
                    # Level minus threshold equals the drawdown, so the closed
                    # form prices a barrier `drawdown` below the current level.
                    preds["gauss_continuous"].append(
                        crossing_probability(cfg.drawdown, 0.0, h, mu[i], sigma[i])
                    )
                else:
                    preds["gauss_continuous"].append(
                        crossing_probability(values[i], barrier, h, mu[i], sigma[i])
                    )
                x = x_all[i]
                for name in ("gauss_discrete", "filtered_empirical"):
                    key = (name, int(bidx[k]))
                    if key not in curves:
                        preds[name].append(np.nan)
                        continue
                    g, p = curves[key]
                    preds[name].append(1.0 if x <= 0 else float(np.interp(x, g, p)))
                if cfg.barrier_mode == "drawdown":
                    # Momentum analogue of the below-barrier alert: fire if the
                    # level already fell that much over the previous h hours.
                    preds["persistence_alert"].append(
                        1.0
                        if i >= h
                        and np.isfinite(values[i - h])
                        and values[i - h] - values[i] >= cfg.drawdown
                        else 0.0
                    )
                else:
                    preds["persistence_alert"].append(1.0 if below[i] else 0.0)
                preds["base_rate"].append(rate)
        out[h] = {
            "y": np.array(ys),
            "idx": np.array(idxs, dtype=int),
            "x": x_all[np.array(idxs, dtype=int)] if idxs else np.array([]),
            "m": m_all[np.array(idxs, dtype=int)] if idxs else np.array([]),
            "sigma": sigma[np.array(idxs, dtype=int)] if idxs else np.array([]),
            "level": values[np.array(idxs, dtype=int)] if idxs else np.array([]),
            **{k: np.array(v) for k, v in preds.items()},
        }
    return barrier, out


def boundary_rows(
    y: pd.Series, barrier: float, cfg: StoppingConfig, device: str
) -> tuple[list[dict], dict[int, dict[float, np.ndarray]]]:
    """Exercise boundaries per horizon and cost ratio, in level and volatility units.

    The boundary is computed once per device from the full training history of
    the last fold, which is the estimate a deployed rule would hold at the end
    of the record. Reported both standardized (comparable across probes) and in
    moisture units at the median holdout volatility (readable by a grower).
    """
    splits = expanding_splits(len(y), cfg.n_folds)
    purged = purged_train_slice(splits[-1][0], max(cfg.horizons_h) - 1)
    z_pool = standardized_pool(
        y.iloc[: purged.stop], cfg.sigma_halflife_h, cfg.mu_halflife_h, cfg.min_pairs
    )
    if len(z_pool) < 48:
        return [], {}
    shape = unit_shape(z_pool, 256)
    sigma = ewma_volatility_series(y, cfg.sigma_halflife_h, cfg.min_pairs)
    mu = ewma_drift_series(y, cfg.mu_halflife_h, cfg.min_pairs)
    te = splits[-1][1]
    sig_med = float(np.nanmedian(sigma.to_numpy()[te.start : te.stop]))
    m_med = float(np.nanmedian((mu / sigma).to_numpy()[te.start : te.stop]))

    rows, curves = [], {}
    max_h = max(cfg.horizons_h)
    for c in cfg.cost_ratios:
        # Standardized problem: barrier at 0, unit volatility, drift m_med.
        xb = exercise_boundary(m_med + shape, 0.0, max_h, c, 12.0 + abs(m_med) * max_h)
        curves.setdefault(0, {})[c] = xb
        for h in cfg.horizons_h:
            x_star = float(xb[h - 1])
            rows.append(
                {
                    "device": device,
                    "barrier": barrier,
                    "horizon_h": h,
                    "cost_ratio": c,
                    "delay_h": 0,
                    "boundary_sigmas": x_star,
                    "sigma_median": sig_med,
                    "boundary_level": barrier + x_star * sig_med,
                    "premium_level": x_star * sig_med,
                }
            )
        # Delayed-response boundaries at one representative cost ratio only, so
        # the table stays small. Delay 0 is already the row emitted above.
        if not np.isclose(c, 0.1):
            continue
        for d in cfg.delay_hours_h:
            if d == 0:
                continue
            xbd = exercise_boundary_delayed(
                m_med + shape, 0.0, max_h, c, d, 12.0 + abs(m_med) * max_h
            )
            x_star = float(xbd[max_h - 1])
            rows.append(
                {
                    "device": device,
                    "barrier": barrier,
                    "horizon_h": max_h,
                    "cost_ratio": c,
                    "delay_h": d,
                    "boundary_sigmas": x_star,
                    "sigma_median": sig_med,
                    "boundary_level": barrier + x_star * sig_med,
                    "premium_level": x_star * sig_med,
                }
            )
    return rows, curves


def value_rows(res: dict[str, np.ndarray], device: str, h: int, alphas: list[float]) -> list[dict]:
    """Cost-loss economic value of each decision rule across the ratio grid."""
    y = res["y"]
    if len(y) == 0:
        return []
    rules = {
        "bayes_gauss_continuous": res["gauss_continuous"],
        "bayes_gauss_discrete": res["gauss_discrete"],
        "bayes_filtered_empirical": res["filtered_empirical"],
    }
    rows = []
    for a in alphas:
        for name, p in rules.items():
            if not np.isfinite(p).all():
                continue
            rows.append(
                {
                    "device": device,
                    "horizon_h": h,
                    "alpha": a,
                    "rule": name,
                    "base_rate": float(y.mean()),
                    "alert_rate": float((p > a).mean()),
                    "value": economic_value(p > a, y, a),
                }
            )
        rows.append(
            {
                "device": device,
                "horizon_h": h,
                "alpha": a,
                "rule": "persistence_alert",
                "base_rate": float(y.mean()),
                "alert_rate": float((res["persistence_alert"] > 0.5).mean()),
                "value": economic_value(res["persistence_alert"] > 0.5, y, a),
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?", default="configs/d2_irrigation/stopping.yaml")
    ap.add_argument("--no-mlflow", action="store_true")
    args = ap.parse_args()

    cfg = StoppingConfig(**load_config(Path(args.config)))
    seed = seed_everything()

    print(f"loading soil probes (barrier_mode={cfg.barrier_mode})...")
    frames = load_soil_probe_frames()
    per_device, barriers, brows = {}, {}, []
    for device, frame in frames.items():
        s = frame["soil_water"]
        barriers[device], per_device[device] = evaluate_device(s, cfg)
        r, _ = boundary_rows(s, barriers[device], cfg, device)
        brows.extend(r)
        counts = {h: int(per_device[device][h]["y"].sum()) for h in cfg.horizons_h}
        n = {h: len(per_device[device][h]["y"]) for h in cfg.horizons_h}
        print(f"  {device}: barrier {barriers[device]:.2f}  crossings {counts} of {n}")

    rows, vrows = [], []
    for device, res in per_device.items():
        for h in cfg.horizons_h:
            y = res[h]["y"]
            if len(y) == 0:
                continue
            for model in PROB_MODELS:
                p = res[h][model]
                if not np.isfinite(p).all():
                    continue
                rows.append(
                    {
                        "device": device,
                        "barrier_mode": cfg.barrier_mode,
                        "barrier": barriers[device],
                        "model": model,
                        "horizon_h": h,
                        "n": len(y),
                        "n_cross": int(y.sum()),
                        "base_rate": float(y.mean()),
                        "brier": brier(y, p),
                        "log_loss": log_loss(y, p),
                    }
                )
            vrows.extend(value_rows(res[h], device, h, cfg.cost_ratios))

    results = (
        pd.DataFrame(rows).sort_values(["horizon_h", "device", "model"]).reset_index(drop=True)
    )
    # Brier skill of each variant against the incumbent Gaussian closed form.
    # The floor keeps a near-zero incumbent Brier (down to 1e-30 on degenerate
    # cells) from turning rounding noise into skill values of astronomical size.
    base = results[results.model == "gauss_continuous"].set_index(["device", "horizon_h"]).brier
    results["brier_skill_vs_gauss_cont"] = [
        1.0 - r.brier / base.loc[(r.device, r.horizon_h)]
        if base.loc[(r.device, r.horizon_h)] > 1e-6
        else np.nan
        for r in results.itertuples()
    ]
    boundaries = pd.DataFrame(brows)
    values = pd.DataFrame(vrows)

    print("\n" + results.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nexercise boundaries (level units at median holdout volatility):")
    print(boundaries.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    ASSETS.mkdir(parents=True, exist_ok=True)
    # Drawdown is the primary mode and owns the unsuffixed filenames.
    suffix = {"drawdown": "", "fixed": "_fixed", "quantile": "_quantile"}[cfg.barrier_mode]
    results.to_csv(ASSETS / f"d2_stopping_results{suffix}.csv", index=False, float_format="%.6f")
    boundaries.to_csv(
        ASSETS / f"d2_stopping_boundaries{suffix}.csv", index=False, float_format="%.6f"
    )
    values.to_csv(ASSETS / f"d2_stopping_value{suffix}.csv", index=False, float_format="%.6f")
    print(f"\nwrote 3 CSVs to {ASSETS}/ with suffix '{suffix or '(none)'}'")

    if not args.no_mlflow:
        try:
            import mlflow

            mlflow.set_experiment("d2_irrigation")
            with mlflow.start_run(run_name=f"stopping-{cfg.barrier_mode}") as run:
                mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
                for r in results.itertuples():
                    tag = f"{r.device}_{r.model}_{r.horizon_h}h"
                    mlflow.log_metric(f"brier_{tag}", r.brier)
                    mlflow.log_metric(f"logloss_{tag}", r.log_loss)
                print(f"mlflow run: {run.info.run_id}")
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
