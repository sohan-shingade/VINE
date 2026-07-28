"""Validate and execute committed notebooks without writing outputs back."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOKS = (
    REPO_ROOT / "notebooks/01_irrigation_results.ipynb",
    REPO_ROOT / "notebooks/02_pipeline_datasheet.ipynb",
)


def validate_cleared(path: Path) -> None:
    """Fail when a committed notebook contains execution state or outputs."""
    notebook = nbformat.read(path, as_version=4)
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        if cell.get("execution_count") is not None or cell.get("outputs"):
            raise ValueError(f"{path}: code cell {index} contains committed outputs")


def execute(path: Path, timeout: int = 600) -> None:
    """Execute a notebook copy from repository root and discard the outputs."""
    notebook = nbformat.read(path, as_version=4)
    old_backend = os.environ.get("MPLBACKEND")
    os.environ["MPLBACKEND"] = "Agg"
    try:
        NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(REPO_ROOT)}},
        ).execute()
    finally:
        if old_backend is None:
            os.environ.pop("MPLBACKEND", None)
        else:
            os.environ["MPLBACKEND"] = old_backend


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebooks", nargs="*", type=Path, default=list(DEFAULT_NOTEBOOKS))
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    for path in args.notebooks:
        validate_cleared(path)
        if not args.check_only:
            execute(path, timeout=args.timeout)
        print(f"ok: {path}")


if __name__ == "__main__":
    main()
