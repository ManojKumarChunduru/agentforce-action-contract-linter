"""Render docs/assets/architecture.mmd to a committed SVG that works as <img src> on GitHub.

GitHub's own Mermaid renderer fails intermittently with an error from inside its lazily loaded
code, and nothing in the repository can fix that. So the diagram is rendered here, committed, and
embedded as an image. Three post-processing steps, each from a real rendering failure:
htmlLabels off so the SVG is well-formed XML, intrinsic width and height from the viewBox so a
browser has an aspect ratio, and an opaque light background so labels stay legible in dark mode.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "docs" / "assets" / "architecture.mmd"
TARGET = REPO / "docs" / "assets" / "architecture.svg"
MANIFEST = REPO / "docs" / "assets" / "architecture.manifest.json"
BACKGROUND = "#f8fafc"


def main() -> int:
    mmdc = shutil.which("mmdc")
    if mmdc is None:
        print(
            "render_architecture: mmdc (mermaid-cli) is not installed; nothing rendered",
            file=sys.stderr,
        )
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "config.json"
        config.write_text(
            json.dumps(
                {
                    "theme": "neutral",
                    # both levels: mermaid-cli reads the top-level key, the renderer the nested one
                    "htmlLabels": False,
                    "flowchart": {"htmlLabels": False, "curve": "basis"},
                    "themeVariables": {
                        "fontFamily": "Helvetica, Arial, sans-serif",
                        "fontSize": "14px",
                    },
                }
            )
        )
        raw = Path(tmp) / "out.svg"
        subprocess.run(
            [mmdc, "-i", str(SOURCE), "-o", str(raw), "-c", str(config), "-b", BACKGROUND],
            check=True,
            capture_output=True,
        )
        svg = raw.read_text(encoding="utf-8")

    if "<foreignObject" in svg:
        raise SystemExit("htmlLabels leaked into the SVG; it would not load as <img src>")
    m = re.search(r'viewBox="([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)"', svg)
    if not m:
        raise SystemExit("rendered SVG has no viewBox")
    width, height = float(m.group(3)), float(m.group(4))
    # mermaid emits width="100%" and a max-width style, right for a page and wrong for <img>
    svg = re.sub(r'<svg([^>]*?)\swidth="[^"]*"', r"<svg\1", svg, count=1)
    svg = re.sub(r'<svg([^>]*?)\sheight="[^"]*"', r"<svg\1", svg, count=1)
    svg = re.sub(r'<svg([^>]*?)\sstyle="[^"]*"', r"<svg\1", svg, count=1)
    svg = svg.replace("<svg", f'<svg width="{width:.0f}" height="{height:.0f}"', 1)
    if f'fill="{BACKGROUND}"' not in svg and BACKGROUND not in svg:
        rect = (
            f'<rect x="{m.group(1)}" y="{m.group(2)}" width="{width}" height="{height}" '
            f'fill="{BACKGROUND}"/>'
        )
        svg = re.sub(r"(<svg[^>]*>)", rf"\1{rect}", svg, count=1)
    TARGET.write_text(svg, encoding="utf-8")
    MANIFEST.write_text(
        json.dumps(
            {
                "source": str(SOURCE.relative_to(REPO)),
                "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "target": str(TARGET.relative_to(REPO)),
                "width": int(width),
                "height": int(height),
                "htmlLabels": False,
                "background": BACKGROUND,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"rendered {TARGET.relative_to(REPO)} ({width:.0f}x{height:.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
