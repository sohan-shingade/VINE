"""Typed config for CV experiments (validates configs/d3_vision/*.yaml)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class ChannelSpec(BaseModel):
    """One input channel, sourced from a single band of one raster.

    The order of `CVConfig.channels` is the tensor channel order, so the config
    is the record of what the model actually saw.
    """

    name: str
    raster: str
    band: int = Field(default=1, ge=1)


class CVConfig(BaseModel):
    """Config for a D3 patch-classification run.

    The proposal's target input is 7 channels (R,G,B,NIR,RedEdge,NDVI,NDRE).
    `in_channels` follows `channels`, so a run restricted to the layers that
    exist locally is expressed by listing only those layers.
    """

    task: str = "stress"  # stress | pest | yield
    backbone: str = "resnet50"  # resnet50 | efficientnet_b0
    in_channels: int = 7  # R,G,B,NIR,RedEdge,NDVI,NDRE
    num_classes: int = 3
    patch_size: int = Field(default=256, ge=32)
    batch_size: int = Field(default=32, ge=1)
    lr: float = 3e-4
    weight_decay: float = 1e-4
    epochs: int = Field(default=30, ge=1)
    pretrained: bool = True
    seed: int = 42

    # Pseudo-label dataset. Weak labels are quantiles of per-patch mean
    # `label_channel`; see docs/models/plant-health/cnn-pseudolabel.md.
    acquisition: str = ""
    blocks_path: Path = Path("data/raw/imagery/IHV-2026-05-26.kmz")
    channels: list[ChannelSpec] = []
    label_channel: str = "NDVI"
    label_quantiles: tuple[float, ...] = (1 / 3, 2 / 3)
    class_names: tuple[str, ...] = ("stressed", "mid", "healthy")
    max_patches_per_block: int = Field(default=32, ge=1)
    min_valid_fraction: float = Field(default=0.98, ge=0.0, le=1.0)
    val_block_fraction: float = Field(default=0.25, gt=0.0, lt=1.0)
    flip_augment: bool = True
    patch_cache: Path = Path("data/processed/d3_patches.npy")
    checkpoint_path: Path = Path("models/d3_vision/cnn_pseudolabel.pt")
    mlflow_experiment: str = "d3_vision"

    @model_validator(mode="after")
    def validate_shape(self) -> CVConfig:
        if self.channels:
            names = [c.name for c in self.channels]
            if len(set(names)) != len(names):
                raise ValueError(f"duplicate channel names: {names}")
            if self.in_channels != len(names):
                raise ValueError(f"in_channels={self.in_channels} but {len(names)} channels listed")
            if self.label_channel not in names:
                raise ValueError(f"label_channel {self.label_channel!r} not in channels {names}")
        if self.num_classes != len(self.label_quantiles) + 1:
            raise ValueError("num_classes must equal len(label_quantiles) + 1")
        if len(self.class_names) != self.num_classes:
            raise ValueError("class_names must have num_classes entries")
        if list(self.label_quantiles) != sorted(self.label_quantiles):
            raise ValueError("label_quantiles must be ascending")
        if any(q <= 0.0 or q >= 1.0 for q in self.label_quantiles):
            raise ValueError("label_quantiles must lie strictly between 0 and 1")
        return self
