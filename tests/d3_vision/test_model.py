"""Tests for the D3 N-channel backbone adapter.

`adapt_stem` is checked directly on a small conv so the fast suite covers the
weight-copy contract without building a backbone. The full `build_model` calls
construct real torchvision backbones and are marked `slow`; they always run
with `pretrained=False` so no test needs the network.
"""

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")

from vine.d3_vision.config import CVConfig  # noqa: E402
from vine.d3_vision.model import adapt_stem, build_model  # noqa: E402


def _stem(in_channels=3, bias=False):
    conv = torch.nn.Conv2d(in_channels, 8, kernel_size=7, stride=2, padding=3, bias=bias)
    with torch.no_grad():
        conv.weight.copy_(
            torch.arange(conv.weight.numel(), dtype=torch.float32).reshape_as(conv.weight)
        )
    return conv


def test_adapt_stem_widens_to_seven_channels_and_keeps_geometry():
    conv = _stem()
    new = adapt_stem(conv, 7)
    assert new.in_channels == 7
    assert new.out_channels == conv.out_channels
    assert new.kernel_size == conv.kernel_size
    assert new.stride == conv.stride
    assert new.padding == conv.padding
    assert new(torch.zeros(2, 7, 64, 64)).shape == (2, 8, 32, 32)


def test_adapt_stem_copies_pretrained_rgb_into_channels_zero_to_two():
    conv = _stem()
    new = adapt_stem(conv, 7)
    assert torch.equal(new.weight[:, :3], conv.weight)
    # The four extra channels are freshly initialized, not zeros or copies.
    assert not torch.allclose(new.weight[:, 3:], torch.zeros_like(new.weight[:, 3:]))


def test_adapt_stem_narrows_by_copying_the_leading_pretrained_kernels():
    conv = _stem()
    new = adapt_stem(conv, 2)
    assert new.in_channels == 2
    assert torch.equal(new.weight, conv.weight[:, :2])


def test_adapt_stem_preserves_bias_and_is_a_noop_at_matching_width():
    conv = _stem(bias=True)
    new = adapt_stem(conv, 5)
    assert torch.equal(new.bias, conv.bias)
    assert adapt_stem(conv, 3) is conv


@pytest.mark.slow
@pytest.mark.parametrize("backbone", ["resnet50", "efficientnet_b0"])
def test_build_model_accepts_seven_channels_and_emits_num_classes(backbone):
    cfg = CVConfig(backbone=backbone, in_channels=7, num_classes=3, pretrained=False)
    model = build_model(cfg)
    out = model(torch.zeros(1, 7, 64, 64))
    assert out.shape == (1, 3)


@pytest.mark.slow
def test_build_model_follows_the_configured_channel_count():
    channels = [
        {"name": "NDVI", "raster": "ndvi.tif"},
        {"name": "NDRE", "raster": "ndre.tif"},
    ]
    cfg = CVConfig(in_channels=2, channels=channels, num_classes=3, pretrained=False)
    model = build_model(cfg)
    assert model.conv1.in_channels == 2
    assert model.fc.out_features == 3
    assert model(torch.zeros(1, 2, 64, 64)).shape == (1, 3)


@pytest.mark.slow
def test_build_model_rejects_an_unknown_backbone():
    with pytest.raises(ValueError, match="unknown backbone"):
        build_model(CVConfig(backbone="vgg16", pretrained=False))
