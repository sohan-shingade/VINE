"""Typed configuration for label-free D3 vegetation-index screening."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, model_validator


class StressRankingConfig(BaseModel):
    acquisition: str
    blocks_path: Path
    ndvi_raster: str
    ndre_raster: str
    output_path: Path = Path("data/processed/d3_stress_ranking.csv")
    quantiles: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75)
    ndvi_low_threshold: float = 0.4
    ndre_low_threshold: float = 0.2
    min_valid_pixels: int = Field(default=100, ge=1)
    min_coverage: float = Field(default=0.5, ge=0.0, le=1.0)
    ndvi_weight: float = Field(default=0.5, ge=0.0)
    ndre_weight: float = Field(default=0.5, ge=0.0)
    disagreement_threshold: float = Field(default=10.0, ge=0.0)
    seed: int = 42
    mlflow_experiment: str = "d3_stress_screening"

    @model_validator(mode="after")
    def validate_weights(self) -> StressRankingConfig:
        if self.ndvi_weight + self.ndre_weight <= 0:
            raise ValueError("at least one index weight must be positive")
        return self


def _concern_percentile(values: pd.Series) -> pd.Series:
    """Percentile concern score where smaller index values rank higher."""
    valid = values.dropna()
    out = pd.Series(float("nan"), index=values.index, dtype=float)
    if valid.empty:
        return out
    out.loc[valid.index] = valid.rank(method="average", ascending=False, pct=True)
    return out


def rank_stress_candidates(
    ndvi: pd.DataFrame,
    ndre: pd.DataFrame,
    cfg: StressRankingConfig,
) -> pd.DataFrame:
    """Rank blocks for field review from same-acquisition NDVI/NDRE summaries.

    This is a screening score, not a disease diagnosis. Low-tail fractions and
    medians are ranked within one acquisition so calibration/season effects do
    not masquerade as biological labels.
    """
    required = {"count", "coverage", "q50", "fraction_below"}
    for name, frame in (("ndvi", ndvi), ("ndre", ndre)):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{name} statistics missing: {sorted(missing)}")

    out = ndvi.add_prefix("ndvi_").join(ndre.add_prefix("ndre_"), how="outer")
    out.insert(0, "acquisition", cfg.acquisition)
    out["quality_ok"] = (
        (out["ndvi_count"] >= cfg.min_valid_pixels)
        & (out["ndre_count"] >= cfg.min_valid_pixels)
        & (out["ndvi_coverage"] >= cfg.min_coverage)
        & (out["ndre_coverage"] >= cfg.min_coverage)
    )

    quality = out.loc[out["quality_ok"]]
    ndvi_component = (
        _concern_percentile(quality["ndvi_q50"])
        + quality["ndvi_fraction_below"].rank(method="average", ascending=True, pct=True)
    ) / 2
    ndre_component = (
        _concern_percentile(quality["ndre_q50"])
        + quality["ndre_fraction_below"].rank(method="average", ascending=True, pct=True)
    ) / 2
    weight = cfg.ndvi_weight + cfg.ndre_weight
    out["stress_candidate_score"] = (
        cfg.ndvi_weight * ndvi_component + cfg.ndre_weight * ndre_component
    ) / weight
    out["ndvi_rank"] = ndvi_component.rank(method="min", ascending=False)
    out["ndre_rank"] = ndre_component.rank(method="min", ascending=False)
    out["index_disagreement"] = (out["ndvi_rank"] - out["ndre_rank"]).abs()
    out["disagreement_flag"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    out.loc[quality.index, "disagreement_flag"] = (
        out.loc[quality.index, "index_disagreement"] > cfg.disagreement_threshold
    )
    out["stress_candidate_rank"] = out["stress_candidate_score"].rank(method="min", ascending=False)
    out = out.reset_index(names="block_id")
    return out.sort_values(
        ["quality_ok", "stress_candidate_rank", "block_id"],
        ascending=[False, True, True],
        na_position="last",
    ).reset_index(drop=True)


def screen_rasters(cfg: StressRankingConfig) -> pd.DataFrame:
    """Read NDVI/NDRE windowed by block and return the stress-screening table."""
    from vine.d1_pipeline.geo import load_blocks_kmz, zonal_distribution

    blocks = load_blocks_kmz(cfg.blocks_path)
    ndvi = zonal_distribution(
        cfg.ndvi_raster,
        blocks,
        quantiles=cfg.quantiles,
        low_threshold=cfg.ndvi_low_threshold,
    )
    ndre = zonal_distribution(
        cfg.ndre_raster,
        blocks,
        quantiles=cfg.quantiles,
        low_threshold=cfg.ndre_low_threshold,
    )
    return rank_stress_candidates(ndvi, ndre, cfg)
