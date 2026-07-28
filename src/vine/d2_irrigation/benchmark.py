"""Run the frozen seven-challenger irrigation benchmark for notebook 01."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from vine.common.config import REPO_ROOT, load_config
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.experiment import run_experiment


class BenchmarkChallenger(BaseModel):
    """One challenger and the existing experiment config that defines it."""

    family: str
    model: str
    config: str


class BenchmarkSpec(BaseModel):
    """Frozen mentor-notebook benchmark scope."""

    seed: int = 42
    device: str = "SE01-LS-1"
    alert_devices: list[str] = Field(default_factory=list)
    horizons_h: list[int] = [6, 12, 24, 48]
    irrigate_below: float = 25.0
    n_folds: int = 5
    challengers: list[BenchmarkChallenger]


def load_benchmark_spec(path: str | Path) -> BenchmarkSpec:
    """Load and validate a benchmark manifest."""
    spec = BenchmarkSpec(**load_config(path))
    if len(spec.challengers) != 7:
        raise ValueError(
            f"benchmark must declare exactly seven challengers, got {len(spec.challengers)}"
        )
    families = [c.family for c in spec.challengers]
    if len(set(families)) != len(families):
        raise ValueError("benchmark challenger families must be unique")
    return spec


def run_benchmark(frame: pd.DataFrame, spec: BenchmarkSpec) -> pd.DataFrame:
    """Run seven configured challengers with their matched persistence errors."""
    pieces: list[pd.DataFrame] = []
    baseline_models = {"persistence", "seasonal_naive", "climatology"}
    baseline_added = False
    for challenger in spec.challengers:
        config_path = REPO_ROOT / challenger.config
        values: dict[str, Any] = load_config(config_path)
        values.update(
            device=spec.device,
            horizons_h=spec.horizons_h,
            n_folds=spec.n_folds,
            irrigate_below=spec.irrigate_below,
        )
        cfg = IrrigationConfig(**values)
        result = run_experiment(frame, cfg)
        selected = result[result["model"].eq(challenger.model)].copy()
        if selected.empty:
            raise ValueError(
                f"{challenger.family}: expected result model {challenger.model!r}, "
                f"got {sorted(result.model.unique())}"
            )
        persistence = result[result["model"].eq("persistence")].set_index("horizon_h")
        selected.insert(
            selected.columns.get_loc("mae") + 1,
            "matched_persistence_mae",
            selected["horizon_h"].map(persistence["mae"]),
        )
        selected.insert(0, "family", challenger.family)
        pieces.append(selected)
        if not baseline_added:
            baseline = result[result["model"].isin(baseline_models)].copy()
            baseline.insert(
                baseline.columns.get_loc("mae") + 1,
                "matched_persistence_mae",
                baseline["horizon_h"].map(persistence["mae"]),
            )
            baseline.insert(0, "family", "baseline")
            pieces.append(baseline)
            baseline_added = True
    table = pd.concat(pieces, ignore_index=True)
    return table.sort_values(
        ["horizon_h", "skill_vs_persistence", "family", "model"],
        ascending=[True, False, True, True],
    ).reset_index(drop=True)
