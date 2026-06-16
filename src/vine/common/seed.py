"""Reproducible seeding. Call `seed_everything()` at the top of every run.

Determinism is a project rule — every experiment must be reproducible from
its config + seed alone (see docs/adr/0005-experiment-tracking.md).
"""

from __future__ import annotations

import os
import random

import numpy as np

from vine.common.config import settings


def seed_everything(seed: int | None = None) -> int:
    """Seed Python, NumPy, and (if installed) PyTorch. Returns the seed used."""
    seed = settings.seed if seed is None else seed
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)  # noqa: NPY002 — global seeding is intentional here
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
    return seed
