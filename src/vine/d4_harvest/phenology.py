"""Growing-degree-day phenology context for D4 — label-free climate exploration.

D4 (harvest timing) needs historical harvest dates, yields, and Brix/pH/TA to
learn or validate anything. Those records do not exist in any source we can
reach (docs/STATE.md input #3), so per ADR-0003 D4 is descoped to exploratory.
This module is that exploratory slice: it accumulates growing degree-days from
daily weather and reports **when a season crossed configured literature
phenology bands**. It contains no learned parameters, no labels, and no
readiness or harvest-date prediction — comparing seasons on heat accumulation
is climate context for a human, not a forecast.

Method (standard viticulture): daily GDD = max(mean(Tmax, Tmin) - base, 0) with
base 10 °C, summed over the season window — the Winkler heat-summation index
(Amerine & Winkler 1944; conventionally Apr 1 – Oct 31 in the Northern
Hemisphere). An optional upper cap on Tmax gives the "modified" variant.

Reference bands (configurable; defaults in configs/d4_harvest/gdd_exploration.yaml):
    bloom      ~350 GDD10   — Chardonnay flowering at 350 GDD10 in Van Leeuwen
                              et al., "Heat requirements for grapevine varieties"
                              (IVES OpenScience), where flowering spans
                              321–414 GDD10 across cultivars; Bavaresco et al.
                              (2019, BIO Web Conf. 12, 01010) observed mid-bloom
                              at ~350 GDD10 for Chardonnay.
    veraison   ~1100–1250 GDD10 — véraison spans 908–1250 GDD10 across cultivars
                              (Van Leeuwen et al.); Bavaresco et al. report
                              mid-véraison at 1165 GDD10 for Chardonnay.
    Both papers accumulate from **Jan 1**, not Apr 1, so under an Apr 1 start
    these thresholds are reached slightly later than published. Treat them as
    order-of-magnitude context, never as calibrated local phenology.

Iron Horse grows Chardonnay and Pinot Noir for sparkling wine, which is picked
early (~17–21 °Brix) to keep acidity, i.e. before still-wine maturity. We found
no peer-reviewed °C-GDD threshold for a sparkling pick, so any "harvest band"
in the config is an explicit placeholder awaiting mentor harvest records — it
is not evidence and must be calibrated before use.

Gaps are flagged, never imputed (repo rule): a missing weather day yields a NaN
daily contribution, and the cumulative curve is reported alongside a running
count of missing days, so a gapped trajectory reads as a lower bound.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from pydantic import BaseModel, Field, model_validator

# Winkler climate regions, in °C growing-degree-days over Apr 1 – Oct 31
# (Amerine & Winkler 1944; the classic bounds are °F-days: 2500/3000/3500/4000).
WINKLER_REGIONS: tuple[tuple[str, float], ...] = (
    ("Region I", 1389.0),
    ("Region II", 1667.0),
    ("Region III", 1944.0),
    ("Region IV", 2222.0),
    ("Region V", float("inf")),
)


class PhenologyBand(BaseModel):
    """One literature GDD band, e.g. véraison at 1100–1250 GDD10."""

    name: str
    gdd_start: float = Field(ge=0.0)
    gdd_end: float | None = Field(default=None, ge=0.0)
    source: str = ""

    @model_validator(mode="after")
    def validate_span(self) -> PhenologyBand:
        if self.gdd_end is not None and self.gdd_end < self.gdd_start:
            raise ValueError(f"band {self.name}: gdd_end must be >= gdd_start")
        return self


class Season(BaseModel):
    """One accumulation window, e.g. 2025-04-01 .. 2025-10-31."""

    label: str
    start: str
    end: str


def daily_gdd(
    temp_max: pd.Series,
    temp_min: pd.Series,
    *,
    base: float = 10.0,
    upper_cap: float | None = None,
) -> pd.Series:
    """Daily GDD contribution: max(mean(Tmax, Tmin) - base, 0), in °C-days.

    Args:
        temp_max: Daily maximum temperature (°C), indexed by date.
        temp_min: Daily minimum temperature (°C), same index.
        base: Base temperature; 10 °C is the viticulture standard.
        upper_cap: Optional cap applied to both temperatures before averaging
            (the "modified" GDD variant, commonly 30 °C). None = uncapped.

    Returns:
        Series of daily contributions. Days with a missing Tmax or Tmin stay
        NaN — they are gaps, not zeros.
    """
    if upper_cap is not None:
        temp_max = temp_max.clip(upper=upper_cap)
        temp_min = temp_min.clip(upper=upper_cap)
    mean_temp = (temp_max + temp_min) / 2.0
    return (mean_temp - base).clip(lower=0.0)


def gdd_trajectory(
    weather: pd.DataFrame,
    *,
    start: str,
    end: str,
    base: float = 10.0,
    upper_cap: float | None = None,
) -> pd.DataFrame:
    """Accumulate GDD across one season window on a complete daily grid.

    Args:
        weather: Tidy daily frame from `vine.d1_pipeline.fetch_historical`
            (DatetimeIndex named `date`; columns `temp_max_c`, `temp_min_c`,
            `precip_mm`, `et0_mm`).
        start: Season start date, inclusive ISO `YYYY-MM-DD`.
        end: Season end date, inclusive. Truncated to the last available
            weather day, so a partial season stops where the data does.
        base: GDD base temperature (°C).
        upper_cap: Optional Tmax/Tmin cap before averaging.

    Returns:
        Frame indexed by date with `temp_max_c`, `temp_min_c`, `gdd_day`,
        `gdd_cumulative`, `missing_day`, `missing_days_to_date`. Missing days
        are reindexed in and flagged: `gdd_day` and `gdd_cumulative` are NaN
        there, and accumulation resumes afterwards without filling the gap, so
        a gapped curve is an explicit lower bound (never imputed).
    """
    for column in ("temp_max_c", "temp_min_c"):
        if column not in weather.columns:
            raise ValueError(f"weather frame missing column {column!r}")

    frame = weather.sort_index()
    window = frame.loc[str(start) : str(end)]
    last = window.index.max() if not window.empty else None
    stop = min(pd.Timestamp(end), last) if last is not None else pd.Timestamp(end)
    grid = pd.date_range(pd.Timestamp(start), stop, freq="D", name="date")
    out = window.reindex(grid)[["temp_max_c", "temp_min_c"]]

    out["gdd_day"] = daily_gdd(out["temp_max_c"], out["temp_min_c"], base=base, upper_cap=upper_cap)
    out["missing_day"] = out["gdd_day"].isna()
    out["gdd_cumulative"] = out["gdd_day"].cumsum()  # NaN on gap days: a lower bound
    out["missing_days_to_date"] = out["missing_day"].cumsum().astype(int)
    return out


def band_crossings(trajectory: pd.DataFrame, bands: Sequence[PhenologyBand]) -> pd.DataFrame:
    """First date each band's GDD threshold was reached in one trajectory.

    Args:
        trajectory: Output of `gdd_trajectory`.
        bands: Literature bands to test (see module docstring for sources).

    Returns:
        One row per band per edge (`gdd_start`, and `gdd_end` when set) with
        `band`, `edge`, `gdd_threshold`, `crossed_date`, `day_of_season`,
        `gdd_cumulative`, `missing_days_before`, `complete`. `crossed_date` is
        NaT when the season never reached the threshold. `complete` is False
        when any weather day was missing before the crossing — the real
        crossing could then be earlier than reported.
    """
    cumulative = trajectory["gdd_cumulative"]
    season_start = trajectory.index.min()
    rows: list[dict[str, object]] = []
    for band in bands:
        edges = [("start", band.gdd_start)]
        if band.gdd_end is not None:
            edges.append(("end", band.gdd_end))
        for edge, threshold in edges:
            hit = cumulative[cumulative >= threshold]
            crossed = hit.index.min() if not hit.empty else pd.NaT
            reached = not pd.isna(crossed)
            missing_before = (
                int(trajectory.loc[:crossed, "missing_day"].sum())
                if reached
                else int(trajectory["missing_day"].sum())
            )
            rows.append(
                {
                    "band": band.name,
                    "edge": edge,
                    "gdd_threshold": threshold,
                    "crossed_date": crossed,
                    "day_of_season": (int((crossed - season_start).days) + 1 if reached else None),
                    "gdd_cumulative": (float(cumulative.loc[crossed]) if reached else None),
                    "missing_days_before": missing_before,
                    "complete": missing_before == 0,
                }
            )
    return pd.DataFrame(rows)


def winkler_region(season_gdd: float) -> str:
    """Winkler climate region for a full-season GDD10 total (°C-days)."""
    for name, upper in WINKLER_REGIONS:
        if season_gdd < upper:
            return name
    return WINKLER_REGIONS[-1][0]


class GddExplorationConfig(BaseModel):
    """Typed config for the label-free GDD exploration (no model, no labels)."""

    seasons: list[Season]
    bands: list[PhenologyBand]
    base_temp_c: float = 10.0
    upper_cap_c: float | None = None
    lat: float | None = None
    lon: float | None = None
    snapshot_csv: str | None = None  # optional local daily-weather CSV
    output_path: str = "data/processed/d4_gdd_trajectories.csv"
    crossings_path: str = "data/processed/d4_gdd_crossings.csv"


def explore_seasons(
    weather: pd.DataFrame, cfg: GddExplorationConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build per-season GDD trajectories and band-crossing dates.

    Args:
        weather: Tidy daily weather frame (see `gdd_trajectory`).
        cfg: Seasons, bands, and GDD parameters.

    Returns:
        `(trajectories, crossings)` — the long trajectory table (one row per
        season-day, `season` first) and the crossing table (one row per
        season-band-edge, with the season's observed total and Winkler region).
    """
    trajectories: list[pd.DataFrame] = []
    crossings: list[pd.DataFrame] = []
    for season in cfg.seasons:
        traj = gdd_trajectory(
            weather,
            start=season.start,
            end=season.end,
            base=cfg.base_temp_c,
            upper_cap=cfg.upper_cap_c,
        )
        traj = traj.reset_index()
        traj.insert(0, "season", season.label)
        trajectories.append(traj)

        cross = band_crossings(traj.set_index("date"), cfg.bands)
        cross.insert(0, "season", season.label)
        total = float(traj["gdd_cumulative"].max()) if not traj.empty else float("nan")
        # A season is only classifiable once its whole window is observed.
        partial = traj.empty or traj["date"].max() < pd.Timestamp(season.end)
        cross["season_gdd_total"] = total
        cross["season_days"] = len(traj)
        cross["season_missing_days"] = int(traj["missing_day"].sum())
        cross["season_partial"] = partial
        cross["winkler_region"] = "n/a (partial season)" if partial else winkler_region(total)
        crossings.append(cross)

    return pd.concat(trajectories, ignore_index=True), pd.concat(crossings, ignore_index=True)
