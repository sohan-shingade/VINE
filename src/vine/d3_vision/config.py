"""Typed config for CV experiments (validates configs/cv/*.yaml)."""

from __future__ import annotations

from pydantic import BaseModel


class CVConfig(BaseModel):
    task: str = "stress"  # stress | pest | yield
    backbone: str = "resnet50"  # resnet50 | efficientnet_b0
    in_channels: int = 7  # R,G,B,NIR,RedEdge,NDVI,NDRE
    num_classes: int = 3  # healthy | mild | severe
    patch_size: int = 256
    batch_size: int = 32
    lr: float = 3e-4
    epochs: int = 30
    pretrained: bool = True
    pseudo_label_ndvi_threshold: float = 0.4  # weak labels when annotations scarce
