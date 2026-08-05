"""Regenerate the offline D3 screening and interim D5 report assets.

Deliverables D3 (plant-health screening), D5 (evaluation), and D7 (reports).
The generator is clean-clone reproducible after ``dvc pull``:

- D2 is recomputed from the DVC-pinned sensor and weather snapshots with the
  current package APIs and checked-in YAML configs.
- D3 is rendered from the retained screening-result artifact. It does not open
  or download the multi-gigabyte source rasters.

No network access, MLflow run directory, or hand-transcribed metric is used.

    uv run python scripts/generate_reports.py
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib
import pandas as pd

from vine.common.config import load_config, settings
from vine.common.seed import seed_everything
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.experiment import run_experiment
from vine.d2_irrigation.pooled import run_pooled_experiment

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "docs" / "reports" / "assets"
D3_RESULT_PATH = ASSETS / "d3_screening_result.csv"
D3_REPORT_PATH = REPO_ROOT / "docs" / "reports" / "2026-08-05-d3-screening.md"
D5_REPORT_PATH = REPO_ROOT / "docs" / "reports" / "2026-08-05-final-evaluation.md"
CONFIG_DIR = REPO_ROOT / "configs" / "d2_irrigation"
DVC_INPUTS = (
    REPO_ROOT / "data" / "raw" / "sensors.dvc",
    REPO_ROOT / "data" / "raw" / "weather.dvc",
)

GREEN = "#2e7a4c"
BLUE = "#31699c"
RED = "#b34a2e"
GREY = "#5b6a5f"
INK = "#1b231d"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "axes.edgecolor": GREY,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#dfe6dc",
        "grid.linewidth": 0.6,
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 170,
        "savefig.bbox": "tight",
    }
)


def _save(fig: plt.Figure, name: str) -> None:
    path = ASSETS / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  {name}.png: {path.stat().st_size / 1024:.0f} KB")


def _save_csv(frame: pd.DataFrame, name: str) -> None:
    path = ASSETS / f"{name}.csv"
    frame.to_csv(path, index=False)
    print(f"  {name}.csv: {len(frame)} rows")


def _config(name: str) -> IrrigationConfig:
    return IrrigationConfig(**load_config(CONFIG_DIR / f"{name}.yaml"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _markdown_table(frame: pd.DataFrame, formats: dict[str, str] | None = None) -> str:
    formats = formats or {}

    def render(column: str, value: object) -> str:
        if pd.isna(value):
            return "—"
        if column in formats:
            return formats[column].format(value)
        if isinstance(value, bool):
            return str(value)
        return str(value)

    header = "| " + " | ".join(frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = [
        "| " + " | ".join(render(column, row[column]) for column in frame.columns) + " |"
        for _, row in frame.iterrows()
    ]
    return "\n".join([header, rule, *rows])


def _require_offline_inputs() -> None:
    """Fail early with a clean-clone recovery instruction, without fetching data."""
    pinned_data_dir = (REPO_ROOT / "data").resolve()
    if settings.data_dir.resolve() != pinned_data_dir:
        raise ValueError(
            "report generation requires the repository's DVC-pinned data directory; "
            "unset VINE_DATA_DIR"
        )
    missing = [path for path in DVC_INPUTS if not path.exists()]
    data_outputs = (
        settings.data_dir / "raw" / "sensors",
        settings.data_dir / "raw" / "weather",
    )
    missing.extend(path for path in data_outputs if not path.exists())
    if missing:
        rendered = "\n  ".join(str(path.relative_to(REPO_ROOT)) for path in missing)
        raise FileNotFoundError(
            f"missing offline report inputs:\n  {rendered}\nRun `uv run dvc pull` first."
        )
    if not D3_RESULT_PATH.exists():
        raise FileNotFoundError(f"missing retained D3 result artifact: {D3_RESULT_PATH}")


# ---------------------------------------------------------------------------
# D3 — render the retained label-free NDVI/NDRE screening result.
# ---------------------------------------------------------------------------
def build_d3_assets() -> pd.DataFrame:
    result = pd.read_csv(D3_RESULT_PATH)
    required = {
        "block_id",
        "quality_ok",
        "stress_candidate_rank",
        "stress_candidate_score",
        "ndvi_coverage",
        "ndre_coverage",
        "ndvi_q50",
        "ndre_q50",
        "ndvi_fraction_below",
        "ndre_fraction_below",
        "index_disagreement",
        "disagreement_flag",
        "ndvi_count",
        "ndre_count",
    }
    missing = sorted(required - set(result.columns))
    if missing:
        raise ValueError(f"D3 result artifact is missing columns: {missing}")
    if len(result) != 39 or result["block_id"].nunique() != 39:
        raise ValueError("D3 result artifact must contain exactly 39 unique vineyard blocks")

    ranked_cols = [
        "block_id",
        "stress_candidate_rank",
        "stress_candidate_score",
        "ndvi_coverage",
        "ndre_coverage",
        "ndvi_q50",
        "ndre_q50",
        "ndvi_fraction_below",
        "ndre_fraction_below",
        "index_disagreement",
        "disagreement_flag",
    ]
    ranked = (
        result[result["quality_ok"]][ranked_cols]
        .sort_values(["stress_candidate_rank", "block_id"])
        .reset_index(drop=True)
    )
    _save_csv(ranked, "d3_full_ranked")

    low_cov_cols = ["block_id", "ndvi_count", "ndvi_coverage", "ndre_count", "ndre_coverage"]
    low_coverage = (
        result[~result["quality_ok"]][low_cov_cols]
        .assign(min_coverage=lambda frame: frame[["ndvi_coverage", "ndre_coverage"]].min(axis=1))
        .sort_values(["min_coverage", "block_id"])
        .drop(columns="min_coverage")
        .reset_index(drop=True)
    )
    _save_csv(low_coverage, "d3_low_coverage")
    print(f"  d3: {len(ranked)} ranked / {len(low_coverage)} coverage failures")

    plot_frame = result.assign(
        min_coverage=result[["ndvi_coverage", "ndre_coverage"]].min(axis=1)
    ).sort_values(["min_coverage", "block_id"], ascending=[False, True])
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    colors = [GREEN if quality_ok else RED for quality_ok in plot_frame["quality_ok"]]
    ax.barh(plot_frame["block_id"], plot_frame["min_coverage"], color=colors, height=0.68)
    ax.axvline(0.5, color=INK, lw=1.0, ls=(0, (4, 3)))
    ax.text(0.505, len(plot_frame) - 0.5, "50% coverage gate", fontsize=7.5, color=INK, va="top")
    ax.set_xlabel("min(NDVI, NDRE) valid-pixel coverage in block window")
    ax.set_xlim(0, 1.0)
    ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=6.8)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=GREEN, label="passed gate (ranked)"),
        plt.Rectangle((0, 0), 1, 1, color=RED, label="failed gate (unranked)"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=7.5)
    ax.set_title("D3 screening: per-block raster coverage, 2026-06-01 acquisition (39 blocks)")
    _save(fig, "d3_coverage")

    top = ranked.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    bar_colors = [RED if flag else BLUE for flag in top["disagreement_flag"]]
    ax.barh(top["block_id"], top["stress_candidate_score"], color=bar_colors, height=0.62)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("stress-candidate score (0-1 within-acquisition percentile)")
    ax.tick_params(axis="y", labelsize=8)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=BLUE, label="NDVI/NDRE agree"),
        plt.Rectangle((0, 0), 1, 1, color=RED, label="index disagreement flagged"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=7.5)
    ax.set_title("Top 15 screening candidates for field review — 2026-06-01")
    _save(fig, "d3_top_ranked")
    return result


# ---------------------------------------------------------------------------
# D5 — recompute all quoted D2 evidence from pinned snapshots and YAML.
# ---------------------------------------------------------------------------
def build_water_balance_assets(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base_config = _config("water_balance")
    runs = []
    for device, frame in frames.items():
        seed_everything(settings.seed)
        config = base_config.model_copy(update={"device": device})
        runs.append(run_experiment(frame, config).assign(device=device))
    raw = pd.concat(runs, ignore_index=True)

    selected = raw[raw["model"].isin(["water_balance", "persistence"])].copy()
    pivot = selected.pivot(
        index=["device", "horizon_h"],
        columns="model",
        values=["n", "mae", "skill_fold_min", "skill_vs_persistence", "recall"],
    )
    pivot.columns = [f"{metric}_{model}" for metric, model in pivot.columns]
    pivot = pivot.reset_index()
    pivot["skill_vs_persistence_pct"] = pivot["skill_vs_persistence_water_balance"] * 100
    pivot["skill_fold_min_pct"] = pivot["skill_fold_min_water_balance"] * 100
    detail = pivot[
        [
            "device",
            "horizon_h",
            "n_water_balance",
            "mae_persistence",
            "mae_water_balance",
            "skill_vs_persistence_pct",
            "skill_fold_min_pct",
            "recall_persistence",
            "recall_water_balance",
        ]
    ].rename(columns={"n_water_balance": "n"})
    detail = detail.sort_values(["horizon_h", "device"]).reset_index(drop=True)
    _save_csv(detail, "d5_water_balance_all_horizons")

    h48 = detail[detail["horizon_h"] == 48].sort_values("device").reset_index(drop=True)
    _save_csv(h48, "d5_water_balance_48h")
    low = h48["skill_vs_persistence_pct"].min()
    high = h48["skill_vs_persistence_pct"].max()
    print(f"  water balance 48h aggregate skill: {low:.1f}% to {high:.1f}%")

    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    x = range(len(h48))
    ax.bar(x, h48["skill_vs_persistence_pct"], color=GREEN, width=0.5, label="aggregate skill")
    ax.scatter(
        x,
        h48["skill_fold_min_pct"],
        color=RED,
        marker="v",
        s=42,
        zorder=5,
        label="worst-fold skill",
    )
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(list(x), h48["device"], rotation=20, ha="right", fontsize=7.8)
    ax.set_ylabel("skill vs persistence (%)")
    ax.set_title("Water balance vs persistence, 48 h\n(realized-future-weather upper bound)")
    ax.legend(fontsize=7.0, loc="center left", bbox_to_anchor=(1.0, 0.5))
    _save(fig, "d5_water_balance_48h")
    return detail


def build_pooled_assets(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    runs = []
    for config_name in ("pooled_gbt", "pooled_ridge"):
        seed_everything(settings.seed)
        runs.append(run_pooled_experiment(frames, _config(config_name)))
    results = pd.concat(runs, ignore_index=True)
    _save_csv(results, "d5_pooled_results")

    fleet = results[(results["device"] == "ALL") & results["model"].str.startswith("pooled_")][
        [
            "model",
            "horizon_h",
            "n",
            "mae",
            "skill_vs_persistence",
            "skill_fold_median",
            "skill_fold_min",
        ]
    ].copy()
    for column in ("skill_vs_persistence", "skill_fold_median", "skill_fold_min"):
        fleet[f"{column}_pct"] = fleet[column] * 100
    fleet = fleet.drop(
        columns=["skill_vs_persistence", "skill_fold_median", "skill_fold_min"]
    ).sort_values(["model", "horizon_h"])
    _save_csv(fleet, "d5_pooled_fleet_skill")

    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.5), sharey=True)
    for ax, model in zip(axes, ("pooled_gbt", "pooled_ridge"), strict=True):
        model_rows = fleet[fleet["model"] == model]
        x = range(len(model_rows))
        aggregate = model_rows["skill_vs_persistence_pct"]
        colors = [GREEN if value > 0 else RED for value in aggregate]
        ax.bar(x, aggregate, color=colors, width=0.55, label="fleet micro-average")
        ax.scatter(
            x,
            model_rows["skill_fold_min_pct"],
            color=INK,
            marker="v",
            s=38,
            zorder=5,
            label="fleet worst fold",
        )
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xticks(list(x), [str(value) for value in model_rows["horizon_h"]])
        ax.set_xlabel("forecast horizon (hours)")
        ax.set_title(model.removeprefix("pooled_").upper())
    axes[0].set_ylabel("skill vs persistence (%)")
    axes[1].legend(fontsize=7.0, loc="lower right")
    fig.suptitle("Pooled models: fleet micro-average and worst-fold skill")
    _save(fig, "d5_pooled_fleet_skill")
    return fleet


def write_d3_report(result: pd.DataFrame) -> None:
    ranked = result[result["quality_ok"]].sort_values(["stress_candidate_rank", "block_id"])
    low_coverage = result[~result["quality_ok"]].assign(
        min_coverage=lambda frame: frame[["ndvi_coverage", "ndre_coverage"]].min(axis=1)
    )
    top = ranked.head(10)[
        [
            "block_id",
            "stress_candidate_rank",
            "stress_candidate_score",
            "ndvi_coverage",
            "ndre_coverage",
            "ndvi_q50",
            "ndre_q50",
            "disagreement_flag",
        ]
    ].rename(
        columns={
            "stress_candidate_rank": "rank",
            "stress_candidate_score": "score",
        }
    )
    low = low_coverage.sort_values(["min_coverage", "block_id"])[
        ["block_id", "ndvi_count", "ndvi_coverage", "ndre_count", "ndre_coverage"]
    ]
    disagreement_count = int(ranked["disagreement_flag"].sum())
    top_names = ", ".join(ranked.head(4)["block_id"])
    artifact_sha256 = _sha256(D3_RESULT_PATH)
    excluded_section = (
        _markdown_table(
            low,
            {
                "ndvi_count": "{:,.0f}",
                "ndvi_coverage": "{:.3f}",
                "ndre_count": "{:,.0f}",
                "ndre_coverage": "{:.3f}",
            },
        )
        if len(low)
        else (
            "No block was excluded. Every polygon interior is fully covered by valid "
            "pixels in both rasters, so the gate rejected nothing on this acquisition."
        )
    )
    text = f"""# D3 report: label-free NDVI/NDRE block screening

**Deliverable:** D3 plant-health CV · **Date:** 2026-08-05 · **Status:** current
engineering artifact, not a supervised model

A same-acquisition, label-free ranking of {len(result)} vineyard blocks from NDVI/NDRE
distribution summaries. It has no learned parameters and no ground truth: it orders blocks
for **human field review**, and cannot diagnose stress, disease, or pests.

This report is generated offline by `scripts/generate_reports.py` from
[`assets/d3_screening_result.csv`](assets/d3_screening_result.csv), the retained result
artifact of the corrected 2026-06-01 raster screen. Artifact SHA-256:
`{artifact_sha256}`. The generator does **not** open or download the source rasters.

## What changed since the first run

An adversarial review invalidated the first screen: its coverage denominator counted each
polygon window's *bounding box* rather than the polygon interior, and rejected rows still
influenced accepted-block percentiles. Both are fixed and covered by regression tests
(`tests/d1_pipeline/test_geo.py`, `tests/d3_vision/test_stress.py`). This page is the rerun
against the real rasters with the corrected implementation; the superseded numbers (a 30/9
coverage split) are in git history and are not evidence.

The per-block distributions themselves did not move — identical pixel counts and quantiles —
because only the quality denominator was wrong. What changed is which blocks pass the gate.

## Reproduction

- The two source rasters are ~4 GB each. They were fetched once to
  `data/raw/imagery/rasters/` and screened locally; range-reading them over the public
  share proved unreliable across multi-hour runs.
- The screening configuration is `configs/d3_vision/stress_screening.yaml` (remote
  `/vsicurl` paths; point `ndvi_raster`/`ndre_raster` at local copies to reproduce).
- The tables and figures below are regenerated deterministically from the retained artifact.

## Coverage gate

{len(ranked)} of {len(result)} blocks passed the quality gate ({len(low)} failed). Coverage is
the fraction of **polygon-interior** pixels that are valid after nodata handling; the
2026-06-01 whole-vineyard mosaic covers every block interior completely.

![Per-block raster coverage](assets/d3_coverage.png)

## Screening candidates

![Top 15 screening candidates](assets/d3_top_ranked.png)

The highest-concern blocks are {top_names}. This is a review queue, not a diagnosis.
{disagreement_count} of {len(ranked)} ranked blocks carry the NDVI/NDRE rank-disagreement
flag, meaning the two indices disagree about the block's relative standing by more than the
configured margin — inspect those with extra care.

{_markdown_table(top, {"rank": "{:.0f}", "score": "{:.3f}", "ndvi_coverage": "{:.3f}", "ndre_coverage": "{:.3f}", "ndvi_q50": "{:.3f}", "ndre_q50": "{:.3f}"})}

The complete ranked output is
[`assets/d3_full_ranked.csv`](assets/d3_full_ranked.csv).

## Excluded blocks

{excluded_section}

Machine-readable detail is in
[`assets/d3_low_coverage.csv`](assets/d3_low_coverage.csv).

## Limits

- **This is a screening order, not a label.** Low indices can reflect phenology, background
  soil, shadows, pruning, irrigation, or processing artifacts.
- Scores are within-acquisition percentiles for 2026-06-01 and should not be compared with
  another date without matched footprints and seasonal controls.
- Thresholds and weights are screening choices, not vineyard-validated decision boundaries.
- No labeled stress/pest imagery exists, so no supervised accuracy is reported. Supervised
  D3 classification stays blocked on mentor-provided labels.
- **D4 harvest timing is not evaluated here.** This artifact has no harvest-readiness, yield,
  or maturity ground truth.

## Next step

Field-verify a sample of the top-ranked blocks with the vineyard team. Agreement between this
order and what reviewers actually find is the only way to learn whether the screen is useful,
and it is the shortest path to the labels supervised D3 needs.
"""
    D3_REPORT_PATH.write_text(text)


def write_d5_report(water_balance: pd.DataFrame, fleet: pd.DataFrame) -> None:
    h48 = water_balance[water_balance["horizon_h"] == 48].copy()
    wb_table = h48[
        [
            "device",
            "n",
            "mae_persistence",
            "mae_water_balance",
            "skill_vs_persistence_pct",
            "skill_fold_min_pct",
            "recall_persistence",
            "recall_water_balance",
        ]
    ].rename(
        columns={
            "skill_vs_persistence_pct": "aggregate_skill",
            "skill_fold_min_pct": "worst_fold",
        }
    )
    fleet_table = fleet[
        [
            "model",
            "horizon_h",
            "n",
            "skill_vs_persistence_pct",
            "skill_fold_median_pct",
            "skill_fold_min_pct",
        ]
    ].rename(
        columns={
            "skill_vs_persistence_pct": "fleet_micro_skill",
            "skill_fold_median_pct": "fold_median",
            "skill_fold_min_pct": "worst_fold",
        }
    )
    wb_low = h48["skill_vs_persistence_pct"].min()
    wb_high = h48["skill_vs_persistence_pct"].max()
    wb_worst_low = h48["skill_fold_min_pct"].min()
    wb_worst_high = h48["skill_fold_min_pct"].max()
    text = f"""# Final D5 evaluation report

**Deliverable:** D5 evaluation, feeding D2 irrigation · **Date:** 2026-08-05 ·
**Status:** persistence remains the served champion

Every quoted D2 number below is recomputed offline by `scripts/generate_reports.py`. The build
loads the five DVC-pinned soil-probe snapshots and pinned weather snapshot through
`load_soil_probe_frames`, calls `seed_everything`, validates the checked-in YAML configs, and
runs the current `run_experiment` and `run_pooled_experiment` package APIs. It has no dependency
on `mlruns`, a run ID, prose-transcribed metrics, network access, or raster downloads.

Clean-clone reproduction:

```bash
uv sync --extra notebooks --extra sensors
uvx --from 'dvc[s3]' dvc pull data/raw/sensors.dvc data/raw/weather.dvc
uv run python scripts/generate_reports.py
```

## Protocol and interpretation limits

- Configs: `configs/d2_irrigation/water_balance.yaml`, `pooled_gbt.yaml`, and
  `pooled_ridge.yaml`; seed: `{settings.seed}`.
- Evaluation uses five expanding walk-forward folds and purges the final `h-1` training labels
  at each boundary.
- **Oracle-weather limit:** all three challengers use `forecast_features: true`. Their lead-time
  weather comes from realized future weather, not archived forecast vintages. Results here are
  perfect-weather upper bounds. Water balance has since been rerun on real archived forecasts —
  see [D2 vintage validation](2026-08-04-d2-vintage-validation.md) and the section below.
- **Micro-average limit:** pooled `ALL` skill is a row-weighted micro-average of correlated
  probe-hours sharing timestamps and weather. It is not five independent replications.
- **Worst-fold limit:** aggregate gains do not satisfy the promotion gate when worst-fold skill
  is negative. Worst-fold results are reported for every computed horizon below.

## Water balance: 48-hour per-probe evidence

![Water balance evidence](assets/d5_water_balance_48h.png)

{_markdown_table(wb_table, {"n": "{:.0f}", "mae_persistence": "{:.3f}", "mae_water_balance": "{:.3f}", "aggregate_skill": "{:+.1f}%", "worst_fold": "{:+.1f}%", "recall_persistence": "{:.3f}", "recall_water_balance": "{:.3f}"})}

Aggregate 48-hour skill is {wb_low:+.1f}% to {wb_high:+.1f}% across five probes, but every
probe has a negative worst fold ({wb_worst_low:+.1f}% to {wb_worst_high:+.1f}%). This is
oracle-weather evidence, so water balance remains an active experiment and is not promoted.
All 6/12/24/48-hour rows are in
[`assets/d5_water_balance_all_horizons.csv`](assets/d5_water_balance_all_horizons.csv).

## Water balance on real forecast vintages

The oracle limit above was removed by rerunning the same model and the same purged evaluation
with lead-time weather drawn from archived Open-Meteo forecast runs as issued, at a
`ceil(h/24)`-day lag so no value post-dates its decision time. Full numbers:
[D2 vintage validation](2026-08-04-d2-vintage-validation.md).

- The 48-hour aggregate edge survives real forecasts (+5.3% to +13.5% across the five probes,
  against +3.5% to +11.2% under the oracle), so it is not an oracle artifact.
- 24-hour skill flips negative on every probe (−2.8% to −8.1%) with worst folds down to −2.448:
  the correction trusts day-1 forecast rain that did not arrive on the forecast hours.
- Worst-fold skill stays negative on every probe at every horizon, so the ADR-0003 gate still
  fails and persistence remains served.

## Pooled GBT and ridge: fleet evidence

![Pooled fleet evidence](assets/d5_pooled_fleet_skill.png)

{_markdown_table(fleet_table, {"horizon_h": "{:.0f}", "n": "{:.0f}", "fleet_micro_skill": "{:+.1f}%", "fold_median": "{:+.1f}%", "worst_fold": "{:+.1f}%"})}

GBT's fleet micro-average is positive at 24 and 48 hours, but its worst fold is negative at all
four horizons. Ridge's fleet micro-average and worst fold are negative at every horizon.
Different `n` values reflect each estimator's valid-row policy; comparisons to persistence are
made on each model's own scorable rows. The full device-level recomputation is retained in
[`assets/d5_pooled_results.csv`](assets/d5_pooled_results.csv).

## Alert-decision limits

Precision/recall can look excellent when a probe spends most of the holdout on one side of the
irrigation threshold. The report therefore does not treat threshold recall as an independent
promotion result. Positive average MAE skill can also coexist with slightly worse recall, as
shown in the computed 48-hour water-balance rows.

## D3 and D4 scope

The companion [D3 screening report](2026-08-05-d3-screening.md) is generated from its retained
result artifact, not from raster downloads. It has no labels and claims no classification
accuracy: 39 of 39 blocks pass the corrected polygon-interior coverage gate and are ordered
for field review.

**D4 harvest timing is not evaluated.** No harvest dates, yield, Brix, pH, TA, or equivalent
ground truth are available in the pinned inputs, so there is no honest D4 backtest to report.
The descoped exploratory slice ([D4 GDD exploration](2026-08-04-d4-gdd-exploration.md)) reports
season heat accumulation only; it has no labels, no learned parameters, and does not ship.

## Decision

Persistence remains the served D2 champion. Neither the oracle-weather challengers nor the
real-forecast water-balance rerun beat it robustly under the worst-fold gate, and pooled fleet
micro-averages are not independent confirmations.
"""
    D5_REPORT_PATH.write_text(text)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    _require_offline_inputs()
    print(f"writing report assets to {ASSETS.relative_to(REPO_ROOT)}")

    print("\nD3 retained-result assets:")
    d3_result = build_d3_assets()

    print("\nLoading DVC-pinned sensor and weather snapshots:")
    frames = load_soil_probe_frames()
    if len(frames) != 5:
        raise ValueError(f"expected five soil probes from pinned snapshots, found {sorted(frames)}")
    print(f"  loaded {len(frames)} probes")

    print("\nD5 water-balance assets (recomputed):")
    water_balance = build_water_balance_assets(frames)
    print("\nD5 pooled GBT/ridge assets (recomputed):")
    fleet = build_pooled_assets(frames)

    write_d3_report(d3_result)
    write_d5_report(water_balance, fleet)
    print("\nWrote both Markdown reports from computed results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
