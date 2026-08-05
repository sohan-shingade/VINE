"""Render executed notebooks into wiki pages so reviewers see the figures.

The committed .ipynb files stay output-free (scripts/check_notebooks.py enforces
that). This renders an executed copy to markdown under docs/notebooks/ with PNG
figures written alongside, which is what a reviewer actually reads.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "notebooks"
ASSETS = OUT / "assets"

PAGES = {
    "01_irrigation_results.ipynb": ("01-irrigation-results", "Irrigation results"),
    "02_pipeline_datasheet.ipynb": ("02-pipeline-datasheet", "Pipeline datasheet"),
}

# Wiki pages sit two levels below the repo root, so notebook links need rewriting.
LINK_FIXES = [("](../docs/", "](../")]


def render(source: Path, slug: str, title: str) -> None:
    """Execute a notebook and write it out as a markdown page with figures."""
    notebook = nbformat.read(source, as_version=4)
    NotebookClient(
        notebook,
        timeout=1800,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    ).execute()

    lines = [
        f"# {title}",
        "",
        f"Rendered from `notebooks/{source.name}`. The committed notebook carries no",
        "outputs; this page is the executed view. Regenerate with"
        " `uv run python scripts/render_notebooks.py`.",
        "",
    ]
    figure = 0
    for cell in notebook.cells:
        if cell.cell_type == "markdown":
            text = cell.source
            for old, new in LINK_FIXES:
                text = text.replace(old, new)
            # the page already carries its own H1
            text = re.sub(r"^# ", "## ", text)
            lines += [text, ""]
            continue
        if cell.cell_type != "code":
            continue
        lines += ["```python", cell.source.rstrip(), "```", ""]
        for output in cell.get("outputs", []):
            data = output.get("data", {})
            if "image/png" in data:
                figure += 1
                name = f"{slug}-fig{figure:02d}.png"
                (ASSETS / name).write_bytes(base64.b64decode(data["image/png"]))
                lines += [f"![figure {figure}](assets/{name})", ""]
            elif "text/html" in data:
                lines += [data["text/html"].strip(), ""]
            elif "text/plain" in data:
                lines += ["```", data["text/plain"].rstrip(), "```", ""]
            elif output.get("output_type") == "stream":
                lines += ["```", "".join(output.get("text", "")).rstrip(), "```", ""]

    (OUT / f"{slug}.md").write_text("\n".join(lines).rstrip() + "\n")
    print(f"ok: docs/notebooks/{slug}.md ({figure} figures)")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, (slug, title) in PAGES.items():
        render(ROOT / "notebooks" / name, slug, title)


if __name__ == "__main__":
    main()
