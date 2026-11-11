"""Photograph the real HTML report, framed by heading, and check the verdict badge is visible.

The screenshot in the README is generated from the report the linter actually writes, by this
script, so a reviewer can regenerate it. Three rules, each from an earlier failure: frame by a
named heading rather than a pixel offset so the shot does not drift when a paragraph grows;
`full_page=True` even with a clip, or Chromium clamps the clip to the viewport; and read back the
badge's computed colours, because a CSS specificity collision once rendered a verdict in the same
colour as its background and nothing but a pixel-level check could have seen it.

Requires the `evidence` extra (playwright) and a Chromium that Playwright can launch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "docs" / "evidence"
REPORT_HTML = EVIDENCE / "report.html"
FRAMES = [
    ("report.png", None, "undecidable"),
    ("report-undecidable.png", "undecidable", None),
]


def build_report() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "afcl",
            "lint",
            str(REPO / "fixture"),
            "--format",
            "html",
            "--output",
            str(REPORT_HTML),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 1:
        raise SystemExit(f"expected exit 1 (drift found) from the fixture, got {proc.returncode}")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("capture_screenshots: playwright is not installed (pip install -e '.[evidence]')")
        return 2
    build_report()
    manifest = {"report": str(REPORT_HTML.relative_to(REPO)), "images": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
        page.goto(REPORT_HTML.resolve().as_uri())
        badge = page.evaluate(
            """() => {
              const b = document.querySelector('.badge');
              if (!b) return null;
              const s = getComputedStyle(b);
              return {text: b.textContent, colour: s.color, background: s.backgroundColor,
                      visible: b.offsetWidth > 0 && b.offsetHeight > 0};
            }"""
        )
        if not badge or not badge["visible"] or badge["colour"] == badge["background"]:
            raise SystemExit(f"verdict badge is missing or invisible: {badge}")
        manifest["badge"] = badge
        for filename, start, end in FRAMES:
            box = page.evaluate(
                """([start, end]) => {
                  let top = 0;
                  if (start) {
                    const s = document.getElementById(start);
                    if (!s) return null;
                    top = s.getBoundingClientRect().top + window.scrollY - 12;
                  }
                  let bottom;
                  if (end) {
                    const e = document.getElementById(end);
                    if (!e) return null;
                    bottom = e.getBoundingClientRect().top + window.scrollY - 12;
                  } else {
                    bottom = document.body.scrollHeight;
                  }
                  return {top, bottom};
                }""",
                [start, end],
            )
            if box is None:
                raise SystemExit(
                    f"heading {start!r} or {end!r} no longer exists; report changed shape"
                )
            clip = {"x": 0, "y": box["top"], "width": 1100, "height": box["bottom"] - box["top"]}
            page.screenshot(path=str(EVIDENCE / filename), clip=clip, full_page=True)
            manifest["images"].append(
                {
                    "file": filename,
                    "from_heading": start or "top of page",
                    "to_heading": end or "end of page",
                }
            )
            print(f"captured {filename} ({int(clip['height'])}px tall)")
        browser.close()
    (EVIDENCE / "screenshots.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"badge: {badge['text']} {badge['colour']} on {badge['background']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
