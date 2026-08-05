"""Train the D3 plant-stress CNN on NDVI-quantile pseudo-labels.

    uv run python scripts/d3_pseudolabel_train.py configs/d3_vision/resnet50.yaml

This is a pipeline-validation run, not a demonstration of stress detection. The
labels are quantiles of each patch's mean NDVI, so the target is a function of
the imagery the model is shown, and the trivial baseline that thresholds patch
mean NDVI reproduces the labels exactly by construction. What the run does
establish is that the patch dataset, the N-channel backbone adapter, the
block-level split, and the training/evaluation loop work end to end, and it
leaves a warm-start checkpoint for the day real annotations arrive.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from vine.common.config import load_config
from vine.common.seed import seed_everything
from vine.d3_vision.config import CVConfig
from vine.d3_vision.model import build_model
from vine.d3_vision.pseudolabel import (
    assign_labels,
    load_patch_cache,
    quantile_thresholds,
    split_blocks,
)


def channel_stats(stack: np.ndarray, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-channel mean/std over the training patches only (no val leakage)."""
    subset = np.asarray(stack[rows], dtype=np.float64)
    mean = subset.mean(axis=(0, 2, 3))
    std = subset.std(axis=(0, 2, 3))
    return mean.astype(np.float32), np.maximum(std, 1e-6).astype(np.float32)


def make_batch(stack, rows, mean, std, *, flip, rng):
    """Normalize one batch of cached patches and optionally flip it."""
    import torch

    data = np.asarray(stack[rows], dtype=np.float32)
    data = (data - mean[None, :, None, None]) / std[None, :, None, None]
    if flip:
        if rng.random() < 0.5:
            data = data[:, :, :, ::-1]
        if rng.random() < 0.5:
            data = data[:, :, ::-1, :]
    return torch.from_numpy(np.ascontiguousarray(data))


def evaluate(model, stack, rows, labels, mean, std, cfg) -> tuple[np.ndarray, float]:
    """Return predicted classes and mean cross-entropy over `rows`."""
    import torch

    model.eval()
    preds, losses = [], []
    with torch.no_grad():
        for start in range(0, len(rows), cfg.batch_size):
            chunk = rows[start : start + cfg.batch_size]
            x = make_batch(stack, chunk, mean, std, flip=False, rng=None)
            y = torch.from_numpy(labels[chunk])
            logits = model(x)
            losses.append(float(torch.nn.functional.cross_entropy(logits, y)) * len(chunk))
            preds.append(logits.argmax(1).numpy())
    return np.concatenate(preds), float(np.sum(losses) / len(rows))


def class_report(truth: np.ndarray, preds: np.ndarray, cfg: CVConfig) -> pd.DataFrame:
    """Per-class support, accuracy (recall), precision, and F1."""
    from sklearn.metrics import precision_recall_fscore_support

    labels = list(range(cfg.num_classes))
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, preds, labels=labels, zero_division=0
    )
    return pd.DataFrame(
        {
            "class": list(cfg.class_names),
            "support": support,
            "accuracy": recall,
            "precision": precision,
            "f1": f1,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML CV config")
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    import torch

    cfg = CVConfig(**load_config(Path(args.config)))
    seed_everything(cfg.seed)
    started = time.time()

    _, index = load_patch_cache(cfg)
    train_blocks, val_blocks = split_blocks(
        index["block_id"].tolist(), cfg.val_block_fraction, cfg.seed
    )
    train_rows = np.flatnonzero(index["block_id"].isin(train_blocks).to_numpy())
    val_rows = np.flatnonzero(index["block_id"].isin(val_blocks).to_numpy())

    # Thresholds come from the training patches only, then are applied to val.
    label_means = index[f"mean_{cfg.label_channel}"].to_numpy(dtype=float)
    thresholds = quantile_thresholds(label_means[train_rows], cfg.label_quantiles)
    labels = assign_labels(label_means, thresholds)

    stack = np.load(cfg.patch_cache, mmap_mode="r")
    mean, std = channel_stats(stack, train_rows)
    model = build_model(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    rng = np.random.default_rng(cfg.seed)

    print(
        f"patches {len(index)} | train {len(train_rows)} in {len(train_blocks)} blocks "
        f"| val {len(val_rows)} in {len(val_blocks)} blocks"
    )
    print(
        f"channels {[c.name for c in cfg.channels]} | "
        f"{cfg.label_channel} thresholds {[round(t, 4) for t in thresholds]}"
    )

    history = []
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        shuffled = rng.permutation(train_rows)
        total, correct, running = 0, 0, 0.0
        for start in range(0, len(shuffled), cfg.batch_size):
            chunk = shuffled[start : start + cfg.batch_size]
            x = make_batch(stack, chunk, mean, std, flip=cfg.flip_augment, rng=rng)
            y = torch.from_numpy(labels[chunk])
            optimizer.zero_grad()
            logits = model(x)
            loss = torch.nn.functional.cross_entropy(logits, y)
            loss.backward()
            optimizer.step()
            running += float(loss.detach()) * len(chunk)
            correct += int((logits.argmax(1) == y).sum())
            total += len(chunk)
        val_preds, val_loss = evaluate(model, stack, val_rows, labels, mean, std, cfg)
        val_acc = float((val_preds == labels[val_rows]).mean())
        history.append(
            {
                "epoch": epoch,
                "train_loss": running / total,
                "train_acc": correct / total,
                "val_loss": val_loss,
                "val_acc": val_acc,
            }
        )
        print(
            f"epoch {epoch:2d}  train_loss {running / total:.4f}  train_acc {correct / total:.3f}"
            f"  val_loss {val_loss:.4f}  val_acc {val_acc:.3f}"
        )

    elapsed = time.time() - started
    truth = labels[val_rows]
    report = class_report(truth, val_preds, cfg)
    macro_f1 = float(report["f1"].mean())
    val_acc = float((val_preds == truth).mean())

    # The trivial baseline applies the same NDVI-quantile rule the labels came
    # from, so its agreement is 1.000 by construction. It is the ceiling here.
    baseline_preds = assign_labels(label_means[val_rows], thresholds)
    baseline_acc = float((baseline_preds == truth).mean())

    confusion = pd.crosstab(
        pd.Series(truth, name="pseudo_label"),
        pd.Series(val_preds, name="predicted"),
        dropna=False,
    ).reindex(index=range(cfg.num_classes), columns=range(cfg.num_classes), fill_value=0)

    print("\nheld-out blocks:", ", ".join(val_blocks))
    print(report.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(
        f"\nmacro F1 {macro_f1:.3f} | val accuracy (= agreement with the pseudo-label rule) "
        f"{val_acc:.3f}"
    )
    print(
        f"trivial patch-mean-{cfg.label_channel} baseline accuracy {baseline_acc:.3f} "
        "(exact by construction: it is the labelling rule)"
    )
    print("\nconfusion (rows pseudo-label, cols predicted):")
    print(confusion.to_string())
    print(f"\nwall time {elapsed / 60:.1f} min over {cfg.epochs} epochs on CPU")
    print(
        "\nThis validates the training pipeline on weak labels. It does NOT show "
        "that plant stress can be detected; that needs field-verified labels."
    )

    cfg.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "config": cfg.model_dump(mode="json"),
            "state_dict": model.state_dict(),
            "channel_mean": mean,
            "channel_std": std,
            "label_thresholds": list(thresholds),
            "train_blocks": train_blocks,
            "val_blocks": val_blocks,
        },
        cfg.checkpoint_path,
    )
    print(f"wrote checkpoint {cfg.checkpoint_path}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("(mlflow not installed — skipped logging)")
            return 0
        mlflow.set_experiment(cfg.mlflow_experiment)
        with mlflow.start_run(run_name=f"cnn-pseudolabel-{cfg.acquisition}"):
            mlflow.log_params(
                {
                    **{k: v for k, v in cfg.model_dump(mode="json").items() if k != "channels"},
                    "channels": json.dumps([c.name for c in cfg.channels]),
                    "n_patches": len(index),
                    "n_train_patches": len(train_rows),
                    "n_val_patches": len(val_rows),
                    "train_blocks": json.dumps(train_blocks),
                    "val_blocks": json.dumps(val_blocks),
                    "label_thresholds": json.dumps([round(t, 6) for t in thresholds]),
                }
            )
            mlflow.log_metrics(
                {
                    "val_accuracy": val_acc,
                    "val_macro_f1": macro_f1,
                    "baseline_ndvi_rule_accuracy": baseline_acc,
                    "wall_time_min": elapsed / 60,
                    **{
                        f"f1_{name}": float(v)
                        for name, v in zip(cfg.class_names, report["f1"], strict=True)
                    },
                    **{
                        f"accuracy_{name}": float(v)
                        for name, v in zip(cfg.class_names, report["accuracy"], strict=True)
                    },
                }
            )
            for row in history:
                mlflow.log_metrics(
                    {k: v for k, v in row.items() if k != "epoch"}, step=int(row["epoch"])
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
