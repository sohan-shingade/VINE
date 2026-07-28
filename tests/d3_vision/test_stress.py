"""Tests for label-free D3 vegetation-index stress screening."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from vine.d3_vision.stress import StressRankingConfig, rank_stress_candidates


def _stats(medians, low, *, coverage=1.0, count=1000):
    index = ["A", "B", "C"]
    return pd.DataFrame(
        {
            "count": [count] * 3,
            "coverage": [coverage] * 3,
            "q50": medians,
            "fraction_below": low,
        },
        index=index,
    )


def _cfg(**updates):
    values = {
        "acquisition": "2026-06-01",
        "blocks_path": Path("blocks.kmz"),
        "ndvi_raster": "ndvi.tif",
        "ndre_raster": "ndre.tif",
        "min_valid_pixels": 10,
    }
    values.update(updates)
    return StressRankingConfig(**values)


def test_low_index_block_ranks_as_highest_concern():
    ndvi = _stats([0.2, 0.5, 0.8], [0.8, 0.3, 0.0])
    ndre = _stats([0.1, 0.3, 0.6], [0.9, 0.4, 0.0])
    ranked = rank_stress_candidates(ndvi, ndre, _cfg())
    assert ranked.iloc[0].block_id == "A"
    assert ranked.iloc[0].stress_candidate_rank == 1
    assert ranked.iloc[-1].block_id == "C"


def test_low_coverage_block_is_flagged_not_ranked():
    ndvi = _stats([0.2, 0.5, 0.8], [0.8, 0.3, 0.0])
    ndre = _stats([0.1, 0.3, 0.6], [0.9, 0.4, 0.0])
    ndvi.loc["A", "coverage"] = 0.1
    ranked = rank_stress_candidates(ndvi, ndre, _cfg(min_coverage=0.5)).set_index("block_id")
    assert not bool(ranked.loc["A", "quality_ok"])
    assert np.isnan(ranked.loc["A", "stress_candidate_score"])
    assert np.isnan(ranked.loc["A", "stress_candidate_rank"])
    assert np.isnan(ranked.loc["A", "ndvi_rank"])
    assert np.isnan(ranked.loc["A", "ndre_rank"])
    assert np.isnan(ranked.loc["A", "index_disagreement"])
    assert pd.isna(ranked.loc["A", "disagreement_flag"])


def test_rejected_block_does_not_affect_accepted_scores_or_ordering():
    ndvi = _stats([0.0, 0.3, 0.7], [1.0, 0.7, 0.1])
    ndre = _stats([0.0, 0.2, 0.6], [1.0, 0.8, 0.2])
    ndvi.loc["A", "coverage"] = 0.1
    ndre.loc["A", "coverage"] = 0.1
    cfg = _cfg(min_coverage=0.5)

    with_rejected = rank_stress_candidates(ndvi, ndre, cfg).set_index("block_id")
    accepted_only = rank_stress_candidates(
        ndvi.loc[["B", "C"]], ndre.loc[["B", "C"]], cfg
    ).set_index("block_id")

    columns = [
        "stress_candidate_score",
        "ndvi_rank",
        "ndre_rank",
        "index_disagreement",
        "disagreement_flag",
        "stress_candidate_rank",
    ]
    pd.testing.assert_frame_equal(
        with_rejected.loc[["B", "C"], columns], accepted_only.loc[["B", "C"], columns]
    )
    assert list(with_rejected.index[:2]) == ["B", "C"]


def test_ranking_is_deterministic_for_ties():
    ndvi = _stats([0.5, 0.5, 0.5], [0.2, 0.2, 0.2])
    ndre = ndvi.copy()
    first = rank_stress_candidates(ndvi, ndre, _cfg())
    second = rank_stress_candidates(ndvi.iloc[::-1], ndre.iloc[::-1], _cfg())
    assert list(first.block_id) == ["A", "B", "C"]
    pd.testing.assert_frame_equal(first, second)


def test_index_disagreement_is_flagged():
    ndvi = _stats([0.1, 0.5, 0.9], [0.9, 0.4, 0.0])
    ndre = _stats([0.9, 0.5, 0.1], [0.0, 0.4, 0.9])
    ranked = rank_stress_candidates(ndvi, ndre, _cfg(disagreement_threshold=1)).set_index(
        "block_id"
    )
    assert bool(ranked.loc["A", "disagreement_flag"])
    assert bool(ranked.loc["C", "disagreement_flag"])


def test_config_requires_a_positive_weight():
    with pytest.raises(ValueError, match="weight"):
        _cfg(ndvi_weight=0.0, ndre_weight=0.0)
