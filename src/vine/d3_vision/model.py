"""CNN with an N-channel input adapter over an ImageNet-pretrained backbone (D3).

The first conv of a stock backbone expects 3 channels; we replace it with a conv
taking `cfg.in_channels`. The proposal's target channel order is
(R,G,B,NIR,RedEdge,NDVI,NDRE), so the pretrained RGB kernels are copied into
channels 0 to 2 and any remaining channels get Kaiming-normal init, matching
torchvision's own stem initialization. When a run has fewer than three channels,
the leading pretrained kernels are copied into the channels that exist.
Requires the `vision` extra; torch/torchvision are imported lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch.nn as nn

    from vine.d3_vision.config import CVConfig


def adapt_stem(conv: Any, in_channels: int) -> Any:
    """Return a copy of stem conv `conv` that accepts `in_channels` channels.

    Kernels for channels 0 to 2 are copied from the pretrained RGB kernels (or
    as many as exist, when `in_channels` is smaller); the rest are
    Kaiming-normal initialized. The conv is returned unchanged when it already
    has the requested input width.
    """
    import torch
    import torch.nn as nn

    if conv.in_channels == in_channels:
        return conv
    new = nn.Conv2d(
        in_channels,
        conv.out_channels,
        kernel_size=conv.kernel_size,
        stride=conv.stride,
        padding=conv.padding,
        dilation=conv.dilation,
        groups=conv.groups,
        bias=conv.bias is not None,
    )
    nn.init.kaiming_normal_(new.weight, mode="fan_out", nonlinearity="relu")
    with torch.no_grad():
        copied = min(in_channels, conv.in_channels)
        new.weight[:, :copied] = conv.weight[:, :copied]
        if conv.bias is not None and new.bias is not None:
            new.bias.copy_(conv.bias)
    return new


def build_model(cfg: CVConfig) -> nn.Module:
    """Construct the fine-tuning model from a CVConfig.

    Loads the configured torchvision backbone (ImageNet weights when
    `cfg.pretrained`), swaps its stem conv for a `cfg.in_channels` conv via
    `adapt_stem`, and replaces the classifier head with `cfg.num_classes`
    outputs. Returns an `nn.Module` ready for training.
    """
    import torch.nn as nn
    import torchvision

    if cfg.backbone == "resnet50":
        weights = torchvision.models.ResNet50_Weights.IMAGENET1K_V2 if cfg.pretrained else None
        model = torchvision.models.resnet50(weights=weights)
        model.conv1 = adapt_stem(model.conv1, cfg.in_channels)
        model.fc = nn.Linear(model.fc.in_features, cfg.num_classes)
    elif cfg.backbone == "efficientnet_b0":
        eff_weights = (
            torchvision.models.EfficientNet_B0_Weights.IMAGENET1K_V1 if cfg.pretrained else None
        )
        model = torchvision.models.efficientnet_b0(weights=eff_weights)
        model.features[0][0] = adapt_stem(model.features[0][0], cfg.in_channels)
        head = model.classifier[-1]
        model.classifier[-1] = nn.Linear(head.in_features, cfg.num_classes)
    else:
        raise ValueError(f"unknown backbone {cfg.backbone!r} (resnet50 | efficientnet_b0)")
    return model
