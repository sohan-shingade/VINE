"""Tests for the D3 pseudo-label patch dataset (synthetic arrays only)."""

import numpy as np
import pytest

from vine.d3_vision.config import CVConfig
from vine.d3_vision.pseudolabel import (
    assign_labels,
    quantile_thresholds,
    split_blocks,
    tile_origins,
)


def test_tile_origins_drops_partial_edge_tiles():
    origins = tile_origins(600, 300, 256)
    assert origins == [(0, 0), (256, 0)]
    assert tile_origins(100, 100, 256) == []


def test_tile_origins_rejects_nonpositive_patch_size():
    with pytest.raises(ValueError, match="patch_size"):
        tile_origins(100, 100, 0)


def test_tertile_thresholds_split_the_population_evenly():
    values = np.arange(300, dtype=float)
    thresholds = quantile_thresholds(values, (1 / 3, 2 / 3))
    labels = assign_labels(values, thresholds)
    counts = np.bincount(labels, minlength=3)
    assert counts.tolist() == [100, 100, 100]


def test_assign_labels_orders_low_index_values_as_class_zero():
    labels = assign_labels([0.1, 0.5, 0.9], (0.3, 0.7))
    assert labels.tolist() == [0, 1, 2]
    # A value exactly on a boundary lands in the higher class.
    assert assign_labels([0.3], (0.3, 0.7)).tolist() == [1]


def test_assign_labels_rejects_unsorted_thresholds():
    with pytest.raises(ValueError, match="ascending"):
        assign_labels([0.5], (0.7, 0.3))


def test_quantile_thresholds_rejects_empty_population():
    with pytest.raises(ValueError, match="empty"):
        quantile_thresholds([], (0.5,))


def test_split_blocks_is_disjoint_deterministic_and_covers_every_block():
    blocks = [f"B{i}" for i in range(12)]
    train, val = split_blocks(blocks, 0.25, seed=42)
    assert set(train) | set(val) == set(blocks)
    assert not set(train) & set(val)
    assert len(val) == 3
    assert (train, val) == split_blocks(blocks, 0.25, seed=42)
    assert val != split_blocks(blocks, 0.25, seed=7)[1]


def test_split_blocks_keeps_patches_of_one_block_on_one_side():
    # Patch-level IDs repeat; the split must still be block-level.
    patch_blocks = ["A"] * 30 + ["B"] * 30 + ["C"] * 30 + ["D"] * 30
    train, val = split_blocks(patch_blocks, 0.25, seed=1)
    assert len(train) + len(val) == 4
    assert not set(train) & set(val)


def test_split_blocks_always_populates_both_sides():
    train, val = split_blocks(["A", "B"], 0.01, seed=0)
    assert len(train) == 1 and len(val) == 1


def test_split_blocks_needs_two_blocks():
    with pytest.raises(ValueError, match="two blocks"):
        split_blocks(["A", "A"], 0.5, seed=0)


def _cfg(**updates):
    values = {
        "in_channels": 2,
        "channels": [
            {"name": "NDVI", "raster": "ndvi.tif"},
            {"name": "NDRE", "raster": "ndre.tif"},
        ],
    }
    values.update(updates)
    return CVConfig(**values)


def test_config_channel_count_must_match_in_channels():
    assert _cfg().in_channels == 2
    with pytest.raises(ValueError, match="in_channels"):
        _cfg(in_channels=7)


def test_config_rejects_a_label_channel_that_is_not_an_input():
    with pytest.raises(ValueError, match="label_channel"):
        _cfg(label_channel="RedEdge")


def test_config_class_count_follows_the_quantile_boundaries():
    cfg = _cfg(num_classes=2, label_quantiles=[0.5], class_names=["low", "high"])
    assert cfg.num_classes == 2
    with pytest.raises(ValueError, match="num_classes"):
        _cfg(num_classes=4)


def test_config_rejects_unsorted_or_degenerate_quantiles():
    with pytest.raises(ValueError, match="ascending"):
        _cfg(label_quantiles=[0.7, 0.3])
    with pytest.raises(ValueError, match="between 0 and 1"):
        _cfg(label_quantiles=[0.0, 0.5])
