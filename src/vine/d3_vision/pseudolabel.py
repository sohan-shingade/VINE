"""Pseudo-labelled patch dataset for D3 plant-health CV.

No field-verified stress labels exist yet, so this module implements the
proposal's stated fallback: weak labels derived from vegetation-index
quantiles. Block interiors are tiled into fixed-size patches, each patch is
read windowed from the orthomosaic index layers (the multi-GB rasters are never
loaded whole), and each patch is labelled by which quantile bin its mean
`label_channel` value falls into.

The labels are a function of the imagery itself, so a model trained on them
learns to reproduce the index rule, not plant stress. The purpose is to
exercise the training pipeline end to end and produce a warm-start checkpoint.
Splitting is by block, so validation blocks are spatially unseen.

Serves D3. Heavy libs (rasterio, geopandas, numpy) are imported lazily.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from vine.common.logging import get_logger

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from vine.d3_vision.config import CVConfig

log = get_logger(__name__)


def tile_origins(height: int, width: int, patch_size: int) -> list[tuple[int, int]]:
    """Top-left offsets of a non-overlapping `patch_size` grid over height/width.

    Partial tiles at the right and bottom edges are dropped, so every returned
    origin admits a full patch.
    """
    if patch_size <= 0:
        raise ValueError("patch_size must be positive")
    return [
        (row, col)
        for row in range(0, height - patch_size + 1, patch_size)
        for col in range(0, width - patch_size + 1, patch_size)
    ]


def quantile_thresholds(values: Sequence[float], quantiles: Sequence[float]) -> tuple[float, ...]:
    """Class boundaries at the given quantiles of `values` (pure)."""
    import numpy as np

    array = np.asarray(values, dtype=float)
    if array.size == 0:
        raise ValueError("cannot derive thresholds from an empty population")
    return tuple(float(t) for t in np.quantile(array, list(quantiles)))


def assign_labels(values: Sequence[float], thresholds: Sequence[float]) -> NDArray[np.int64]:
    """Bin `values` into class indices 0..len(thresholds) by ascending threshold.

    Class 0 is the lowest bin (lowest index values, i.e. the most concerning),
    the last class the highest. Boundaries are right-open: a value equal to a
    threshold lands in the higher class.
    """
    import numpy as np

    array = np.asarray(values, dtype=float)
    bounds = np.asarray(thresholds, dtype=float)
    if bounds.size and np.any(np.diff(bounds) < 0):
        raise ValueError("thresholds must be ascending")
    return np.digitize(array, bounds, right=False).astype(np.int64)


def split_blocks(
    block_ids: Sequence[str], val_fraction: float, seed: int
) -> tuple[list[str], list[str]]:
    """Partition unique block IDs into train/val groups (pure, deterministic).

    Splitting on blocks rather than patches keeps every validation patch inside
    a block the model never saw. At least one block goes to each side.
    """
    import numpy as np

    unique = sorted(set(block_ids))
    if len(unique) < 2:
        raise ValueError("need at least two blocks to split")
    n_val = int(round(len(unique) * val_fraction))
    n_val = min(max(n_val, 1), len(unique) - 1)
    order = np.random.default_rng(seed).permutation(len(unique))
    val = sorted(unique[i] for i in order[:n_val])
    train = sorted(unique[i] for i in order[n_val:])
    return train, val


def _block_windows(cfg: CVConfig, source, geometry) -> list[tuple[int, int]]:
    """Row/col offsets of patches fully inside one block polygon and the raster."""
    import rasterio.transform
    from shapely.geometry import box

    transform = source.transform
    height, width = source.shape
    minx, miny, maxx, maxy = geometry.bounds
    top, left = rasterio.transform.rowcol(transform, minx, maxy)
    bottom, right = rasterio.transform.rowcol(transform, maxx, miny)
    size = cfg.patch_size
    origins = []
    for row, col in tile_origins(int(bottom - top), int(right - left), size):
        r, c = int(top) + row, int(left) + col
        if r < 0 or c < 0 or r + size > height or c + size > width:
            continue
        west, north = rasterio.transform.xy(transform, r, c, offset="ul")
        east, south = rasterio.transform.xy(transform, r + size, c + size, offset="ul")
        if geometry.contains(box(west, south, east, north)):
            origins.append((r, c))
    return origins


def _read_patch(sources, cfg: CVConfig, row: int, col: int):
    """Read one aligned multi-channel patch; returns (data, valid_fraction)."""
    import numpy as np
    from rasterio.windows import Window

    size = cfg.patch_size
    window = Window(col, row, size, size)
    planes = []
    valid = np.ones((size, size), dtype=bool)
    for src, channel in zip(sources, cfg.channels, strict=True):
        plane = src.read(channel.band, window=window).astype(np.float32)
        ok = np.isfinite(plane)
        if src.nodata is not None:
            ok &= plane != np.float32(src.nodata)
        valid &= ok
        planes.append(plane)
    data = np.stack(planes)
    data[:, ~valid] = 0.0
    return data, float(valid.mean())


def build_patch_cache(cfg: CVConfig) -> tuple[Path, pd.DataFrame]:
    """Tile block interiors into patches and cache them next to an index frame.

    Writes `cfg.patch_cache` (an (N, C, patch, patch) float32 array) and a
    sibling `.csv` index carrying `block_id`, patch offsets, valid fraction, and
    the per-channel patch means used for pseudo-labelling. Patches below
    `cfg.min_valid_fraction` valid pixels are rejected, and at most
    `cfg.max_patches_per_block` patches are kept per block (seeded shuffle).
    """
    import numpy as np
    import rasterio

    from vine.d1_pipeline.geo import load_blocks_kmz

    if not cfg.channels:
        raise ValueError("cfg.channels is empty; nothing to read")
    blocks = load_blocks_kmz(cfg.blocks_path)
    rng = np.random.default_rng(cfg.seed)
    sources = [rasterio.open(channel.raster) for channel in cfg.channels]
    try:
        first = sources[0]
        for src in sources[1:]:
            if src.shape != first.shape or src.transform != first.transform:
                raise ValueError("channel rasters are not on an identical grid")
        aligned = blocks.to_crs(first.crs)

        records: list[dict[str, object]] = []
        for block_id, geometry in zip(aligned["block_id"], aligned.geometry, strict=True):
            candidates = _block_windows(cfg, first, geometry)
            order = rng.permutation(len(candidates))
            kept = 0
            for position in order:
                if kept >= cfg.max_patches_per_block:
                    break
                row, col = candidates[int(position)]
                data, valid_fraction = _read_patch(sources, cfg, row, col)
                if valid_fraction < cfg.min_valid_fraction:
                    continue
                record: dict[str, object] = {
                    "block_id": block_id,
                    "row_off": row,
                    "col_off": col,
                    "valid_fraction": valid_fraction,
                }
                for channel_index, channel in enumerate(cfg.channels):
                    record[f"mean_{channel.name}"] = float(data[channel_index].mean())
                records.append(record)
                kept += 1
            log.info("tiled block", block_id=block_id, candidates=len(candidates), kept=kept)

        index = pd.DataFrame(records)
        if index.empty:
            raise ValueError("no patches passed the validity gate")
        cfg.patch_cache.parent.mkdir(parents=True, exist_ok=True)
        stack = np.lib.format.open_memmap(
            cfg.patch_cache,
            mode="w+",
            dtype=np.float32,
            shape=(len(index), len(cfg.channels), cfg.patch_size, cfg.patch_size),
        )
        for slot, (patch_row, patch_col) in enumerate(
            zip(index["row_off"], index["col_off"], strict=True)
        ):
            stack[slot], _ = _read_patch(sources, cfg, int(patch_row), int(patch_col))
        stack.flush()
    finally:
        for src in sources:
            src.close()

    index.to_csv(cfg.patch_cache.with_suffix(".csv"), index=False)
    log.info("wrote patch cache", path=str(cfg.patch_cache), patches=len(index))
    return cfg.patch_cache, index


def load_patch_cache(cfg: CVConfig) -> tuple[Path, pd.DataFrame]:
    """Return the cached patch stack and index, building them if absent."""
    csv_path = cfg.patch_cache.with_suffix(".csv")
    if cfg.patch_cache.exists() and csv_path.exists():
        index = pd.read_csv(csv_path)
        log.info("reusing patch cache", path=str(cfg.patch_cache), patches=len(index))
        return cfg.patch_cache, index
    return build_patch_cache(cfg)
