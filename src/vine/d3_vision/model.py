"""CNN with a 7-channel input adapter over an ImageNet-pretrained backbone.

The first conv of a stock backbone expects 3 channels; we replace it with a
7-channel conv (R,G,B,NIR,RedEdge,NDVI,NDRE) and copy the pretrained RGB
weights into the first three input channels. Requires the `cv` extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch.nn as nn

    from vine.d3_vision.config import CVConfig


def build_model(cfg: CVConfig) -> nn.Module:
    """Construct the fine-tuning model from a CVConfig.

    TODO(D3): instantiate backbone via torchvision, swap stem conv to
    `in_channels`, copy pretrained RGB weights, replace classifier head with
    `num_classes`. Returns an nn.Module ready for training.
    """
    raise NotImplementedError("D3: implement 7-channel backbone adapter")
