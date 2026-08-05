"""Walk-forward evaluation of the irrigation clock (D2, survival analysis).

The question every prior D2 layer answers is fixed-horizon; the question a
grower asks is "how many hours until this block needs water?". This runner
scores that question directly, as a censored time-to-event problem:

- The event is a drawdown of `drawdown` units below the decision-time level,
  the same stationary barrier as the stopping layer.
- Every decision hour is used. Windows cut short by a sensor gap or the end of
  the record are right-censored, not dropped, and scoring uses inverse
  probability of censoring weighting (Graf et al. 1999). The stopping layer's
  fully-observed-window rule discards those rows, which conditions on the
  future; this one keeps them.
- Each model outputs a full survival curve S(h), h = 1..max_h, scored by the
  IPCW Brier score integrated over the grid (IBS, lower is better).

Models, causal by construction:

    km-train          Kaplan-Meier curve of the training fold (the survival
                      null: one marginal curve for every hour)
    drydown-clock     deterministic drydown calculator, drop / drying rate
                      (current grower practice as a step-function curve)
    gauss-continuous  closed-form Brownian first passage (the literature's
                      incumbent), one curve per row from causal EWMA mu, sigma
    gauss-discrete    hourly-monitored Gaussian random walk, drift-bucketed
    fhs-discrete      hourly-monitored filtered historical simulation: the
                      training fold's standardized increment shape, rescaled
                      to the row's causal moments
    hazard-glm        discrete-time hazard regression (Singer & Willett): a
                      pooled logistic hazard on the training fold's at-risk
                      hours, with baseline-shape, hour-of-day, drift, and
                      depth covariates (the only model that can see the
                      diurnal phase)
    fhs-hazard-blend  equal-weight average of the fhs-discrete and hazard-glm
                      curves. No fitted weight: the two families have
                      complementary information (volatility shape vs diurnal
                      and seasonal timing), and the Brier score is convex, so
                      the blend is never worse than the average of its members

    uv run python scripts/d2_survival.py
    uv run python scripts/d2_survival.py configs/d2_irrigation/survival.yaml --no-mlflow

Writes deterministic CSVs to docs/reports/assets/ and logs to MLflow.
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
    filtered_increments,
    gaussian_increments,
    standardized_pool,
)
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
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice

ASSETS = Path("docs/reports/assets")
MODELS = (
    "km-train",
    "drydown-clock",
    "gauss-continuous",
    "gauss-discrete",
    "fhs-discrete",
    "hazard-glm",
    "fhs-hazard-blend",
)
# Skill references: the survival null, current practice, and the incumbent
# closed form. A challenger must beat all three to matter.
REFERENCES = ("km-train", "drydown-clock", "gauss-continuous")


class SurvivalConfig(BaseModel):
    drawdown: float = 0.3
    max_h: int = 48
    n_folds: int = 5
    sigma_halflife_h: float = 72.0
    mu_halflife_h: float = 336.0
    min_pairs: int = 24
    n_drift_buckets: int = 24
    report_horizons: list[int] = [6, 12, 24, 48]
    quantiles: list[float] = [0.1, 0.5, 0.9]


def bucket_drifts(m: np.ndarray, n_buckets: int) -> tuple[np.ndarray, np.ndarray]:
    """Assign standardized drifts to equal-count buckets; return (index, centers).

    Same rule as scripts/d2_stopping.py: one backward recursion per bucket
    serves every row whose drift falls in it.
    """
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


def bucketed_survival(
    x: np.ndarray, m: np.ndarray, increments_of: dict[int, np.ndarray], max_h: int
) -> np.ndarray:
    """Survival matrix (n_rows, max_h) from one recursion per drift bucket.

    `x` is the standardized starting height above the barrier (drop / sigma),
    `m` the bucket index per row, `increments_of` the discretized law per
    bucket. Rows whose bucket law is unusable come back NaN.
    """
    out = np.full((len(x), max_h), np.nan)
    for b, inc in increments_of.items():
        rows = np.flatnonzero(m == b)
        if len(rows) == 0 or len(inc) == 0:
            continue
        grid, surv = survival_curve_grid(inc, max_h)
        if len(grid) == 0:
            continue
        for k in range(max_h):
            out[rows, k] = np.interp(x[rows], grid, surv[k])
    return out


def evaluate_device(y: pd.Series, cfg: SurvivalConfig) -> list[dict]:
    """Per-fold IBS and horizon Briers for every model on one probe."""
    values = y.to_numpy(dtype=float)
    hod = y.index.hour.to_numpy()
    sigma = ewma_volatility_series(y, cfg.sigma_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    mu = ewma_drift_series(y, cfg.mu_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    idx_all, time_all, event_all = survival_labels(values, cfg.drawdown, cfg.max_h)
    labeled = {int(i): k for k, i in enumerate(idx_all)}
    # Rows usable by the conditional models: causal moments must exist.
    ok_all = np.isfinite(sigma[idx_all]) & (sigma[idx_all] > 0) & np.isfinite(mu[idx_all])
    rows: list[dict] = []
    for fold, (tr, te) in enumerate(expanding_splits(len(y), cfg.n_folds)):
        purged = purged_train_slice(tr, cfg.max_h - 1)
        train_mask = idx_all < purged.stop
        km_curve = kaplan_meier(time_all[train_mask], event_all[train_mask], cfg.max_h)
        z_pool = standardized_pool(
            y.iloc[: purged.stop], cfg.sigma_halflife_h, cfg.mu_halflife_h, cfg.min_pairs
        )
        tr_sel = train_mask & ok_all
        ridx = idx_all[tr_sel]
        pp_rows, pp_period, pp_died = person_periods(time_all[tr_sel], event_all[tr_sel], cfg.max_h)
        x_tr = cfg.drawdown / sigma[ridx]
        m_tr = mu[ridx] / sigma[ridx]
        hazard = fit_hazard(
            hazard_design(
                pp_period, (hod[ridx][pp_rows] + pp_period) % 24, m_tr[pp_rows], x_tr[pp_rows]
            ),
            pp_died,
        )
        test_idx = np.array(
            [
                i
                for i in range(te.start, te.stop)
                if i in labeled and np.isfinite(sigma[i]) and sigma[i] > 0 and np.isfinite(mu[i])
            ],
            dtype=int,
        )
        if len(test_idx) == 0:
            continue
        pos = np.array([labeled[int(i)] for i in test_idx])
        t, e = time_all[pos], event_all[pos]
        g = censoring_survival(t, e, cfg.max_h)
        x = cfg.drawdown / sigma[test_idx]
        m = mu[test_idx] / sigma[test_idx]
        bidx, centers = bucket_drifts(m, cfg.n_drift_buckets)

        surv: dict[str, np.ndarray] = {}
        surv["km-train"] = np.tile(km_curve, (len(test_idx), 1))
        surv["drydown-clock"] = np.array(
            [clock_survival(mu[i], cfg.drawdown, cfg.max_h) for i in test_idx]
        )
        surv["gauss-continuous"] = np.array(
            [
                [
                    1.0 - crossing_probability(cfg.drawdown, 0.0, h, mu[i], sigma[i])
                    for h in range(1, cfg.max_h + 1)
                ]
                for i in test_idx
            ]
        )
        gauss_laws = {b: gaussian_increments(float(m_c), 1.0) for b, m_c in enumerate(centers)}
        fhs_laws = {
            b: filtered_increments(z_pool, float(m_c), 1.0) for b, m_c in enumerate(centers)
        }
        surv["gauss-discrete"] = bucketed_survival(x, bidx, gauss_laws, cfg.max_h)
        surv["fhs-discrete"] = bucketed_survival(x, bidx, fhs_laws, cfg.max_h)
        surv["hazard-glm"] = hazard_survival(hazard, hod[test_idx], m, x, cfg.max_h)
        surv["fhs-hazard-blend"] = 0.5 * (surv["fhs-discrete"] + surv["hazard-glm"])

        for model in MODELS:
            s = surv[model]
            if not np.isfinite(s).all():
                print(f"    (fold {fold}: {model} skipped, unusable predictions)")
                continue
            bs = censored_brier_curve(t, e, s, g)
            row = {
                "fold": fold,
                "model": model,
                "n": len(test_idx),
                "n_event": int(e.sum()),
                "n_censored": int(((t <= cfg.max_h) & ~e).sum()),
                "ibs": integrated_brier(bs),
            }
            for h in cfg.report_horizons:
                row[f"brier_{h}h"] = float(bs[h - 1])
            rows.append(row)
    return rows


def clock_reading(y: pd.Series, cfg: SurvivalConfig) -> dict:
    """The deployed reading at the last valid hour: FHS quantile times to trigger."""
    values = y.to_numpy(dtype=float)
    last = int(np.flatnonzero(np.isfinite(values))[-1])
    sigma = ewma_volatility_series(y, cfg.sigma_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    mu = ewma_drift_series(y, cfg.mu_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    z_pool = standardized_pool(y, cfg.sigma_halflife_h, cfg.mu_halflife_h, cfg.min_pairs)
    out = {
        "timestamp": str(y.index[last]),
        "level": float(values[last]),
        "mu": float(mu[last]),
        "sigma": float(sigma[last]),
    }
    inc = filtered_increments(z_pool, mu[last] / sigma[last], 1.0)
    grid, surv = survival_curve_grid(inc, cfg.max_h)
    if len(grid) == 0:
        return out
    row = np.array([np.interp(cfg.drawdown / sigma[last], grid, surv[k]) for k in range(cfg.max_h)])
    for q, t_q in zip(cfg.quantiles, quantile_times(row, tuple(cfg.quantiles)), strict=True):
        out[f"t{int(round(q * 100))}_h"] = t_q
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?", default="configs/d2_irrigation/survival.yaml")
    ap.add_argument("--no-mlflow", action="store_true")
    args = ap.parse_args()

    cfg = SurvivalConfig(**load_config(Path(args.config)))
    seed = seed_everything()

    print(f"loading soil probes (drawdown={cfg.drawdown}, max_h={cfg.max_h})...")
    frames = load_soil_probe_frames()
    rows, readings = [], []
    for device, frame in frames.items():
        dev_rows = evaluate_device(frame["soil_water"], cfg)
        for r in dev_rows:
            rows.append({"device": device, **r})
        readings.append({"device": device, **clock_reading(frame["soil_water"], cfg)})
        n_ev = sum(r["n_event"] for r in dev_rows if r["model"] == "fhs-discrete")
        n_ce = sum(r["n_censored"] for r in dev_rows if r["model"] == "fhs-discrete")
        n = sum(r["n"] for r in dev_rows if r["model"] == "fhs-discrete")
        print(f"  {device}: {n} decisions, {n_ev} events, {n_ce} censored inside the window")

    folds = pd.DataFrame(rows).sort_values(["device", "fold", "model"]).reset_index(drop=True)

    # Per-fold skill of every model against each reference, then aggregate.
    # A reference IBS near zero means a degenerate fold (no events, so the
    # trivial "never crosses" prediction is perfect); the ratio is undefined
    # there, and those fold cells are excluded from the skill aggregates. The
    # raw IBS rows stay in the folds CSV either way.
    ref = folds.set_index(["device", "fold", "model"]).ibs
    for name in REFERENCES:
        folds[f"skill_vs_{name}"] = [
            1.0 - r.ibs / ref.loc[(r.device, r.fold, name)]
            if (r.device, r.fold, name) in ref.index and ref.loc[(r.device, r.fold, name)] > 1e-9
            else np.nan
            for r in folds.itertuples()
        ]
        n_excluded = int(folds[f"skill_vs_{name}"].isna().sum())
        if n_excluded:
            print(f"skill_vs_{name}: {n_excluded} fold cells excluded (degenerate reference)")

    def _mean_finite(vals: pd.Series, w: pd.Series) -> float:
        ok = np.isfinite(vals.to_numpy(dtype=float))
        if not ok.any():
            return float("nan")
        return float(np.average(vals.to_numpy(dtype=float)[ok], weights=w.to_numpy()[ok]))

    def _min_finite(vals: pd.Series) -> float:
        ok = np.isfinite(vals.to_numpy(dtype=float))
        return float(vals.to_numpy(dtype=float)[ok].min()) if ok.any() else float("nan")

    summary = (
        folds.groupby(["device", "model"])
        .apply(
            lambda d: pd.Series(
                {
                    "n": d.n.sum(),
                    "n_event": d.n_event.sum(),
                    "ibs": float(np.average(d.ibs, weights=d.n)),
                    **{
                        f"skill_vs_{name}": _mean_finite(d[f"skill_vs_{name}"], d.n)
                        for name in REFERENCES
                    },
                    **{
                        f"worst_fold_vs_{name}": _min_finite(d[f"skill_vs_{name}"])
                        for name in REFERENCES
                    },
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    clock = pd.DataFrame(readings)

    print("\n" + summary.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nclock readings at the last valid hour (hours to a 0.3 drawdown):")
    print(clock.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    ASSETS.mkdir(parents=True, exist_ok=True)
    folds.to_csv(ASSETS / "d2_survival_folds.csv", index=False, float_format="%.6f")
    summary.to_csv(ASSETS / "d2_survival_summary.csv", index=False, float_format="%.6f")
    clock.to_csv(ASSETS / "d2_survival_clock.csv", index=False, float_format="%.6f")
    print(f"\nwrote 3 CSVs to {ASSETS}/")

    if not args.no_mlflow:
        try:
            import mlflow

            mlflow.set_experiment("d2_irrigation")
            with mlflow.start_run(run_name="survival-clock") as run:
                mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
                for rec in summary.to_dict("records"):
                    tag = f"{rec['device']}_{rec['model']}"
                    mlflow.log_metric(f"ibs_{tag}", rec["ibs"])
                    for name in REFERENCES:
                        v = rec[f"worst_fold_vs_{name}"]
                        if np.isfinite(v):
                            mlflow.log_metric(f"worst_fold_vs_{name.replace('-', '_')}_{tag}", v)
                print(f"mlflow run: {run.info.run_id}")
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
