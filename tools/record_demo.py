"""Record the demo GIF as a replay of real captured output, never a hand-written transcript.

Each command is run for real; its stdout, stderr, exit code and wall time are captured and
written to docs/evidence/demo.manifest.json. A self-contained HTML player then types each
command and reveals the captured output paced by that command's measured duration, Playwright
records the page, and ffmpeg transcodes the recording to an MP4 and a two-pass palette GIF that
autoplays inline on GitHub. Every line of terminal text in the GIF came out of a process.

The segments are ordered as the argument, not as a feature list: the verdict first, then the
totals, then the number no other tool reports, then the blind spot, then the receipts.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "docs" / "evidence"
PLAYER = EVIDENCE / "player.html"
MANIFEST = EVIDENCE / "demo.manifest.json"

COMMANDS: list[tuple[str, list[str]]] = [
    ("afcl lint fixture", [sys.executable, "-m", "afcl", "lint", "fixture"]),
    (
        "afcl lint fixture --format json | python -c 'print totals'",
        [
            "bash",
            "-c",
            f"{sys.executable} -m afcl lint fixture --format json | {sys.executable} -c "
            "\"import json,sys; d=json.load(sys.stdin); print(json.dumps(d['totals'], indent=2))\"",
        ],
    ),
    (
        "python experiments/exp02_name_only_review.py",
        [sys.executable, "experiments/exp02_name_only_review.py"],
    ),
    (
        "python experiments/exp03_undecidable.py",
        [sys.executable, "experiments/exp03_undecidable.py"],
    ),
    ("make receipts", ["make", "receipts"]),
]

MAX_LINES = 26


def capture() -> list[dict]:
    # warm the interpreter so the first segment does not pay for the import
    subprocess.run([sys.executable, "-m", "afcl", "classes"], cwd=REPO, capture_output=True)
    segments = []
    for shown, argv in COMMANDS:
        start = time.perf_counter()
        proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
        seconds = time.perf_counter() - start
        out = (proc.stdout + proc.stderr).rstrip("\n").splitlines()
        if len(out) > MAX_LINES:
            out = out[: MAX_LINES - 1] + [f"... ({len(out) - MAX_LINES + 1} more lines)"]
        segments.append(
            {
                "command": shown,
                "argv": argv,
                "exit_code": proc.returncode,
                "seconds": round(seconds, 3),
                "lines": out,
            }
        )
        print(f"captured: {shown} -> exit {proc.returncode} in {seconds:.2f}s, {len(out)} lines")
    return segments


def build_player(segments: list[dict]) -> None:
    template = (Path(__file__).resolve().parent / "demo_player.html").read_text(encoding="utf-8")
    PLAYER.write_text(template.replace("__SEGMENTS__", json.dumps(segments)), encoding="utf-8")


def record() -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": 960, "height": 564},
            record_video_dir=str(EVIDENCE),
            record_video_size={"width": 960, "height": 564},
        )
        page = context.new_page()
        page.goto(PLAYER.resolve().as_uri())
        page.wait_for_function("document.title === 'done'", timeout=180_000)
        video = page.video
        context.close()
        path = Path(video.path())
        browser.close()
    return path


def transcode(webm: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required to transcode the recording")
    mp4 = EVIDENCE / "demo.mp4"
    gif = EVIDENCE / "demo.gif"
    palette = EVIDENCE / "palette.png"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(webm),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "28",
            str(mp4),
        ],
        check=True,
    )
    filters = "fps=6,scale=800:-1:flags=lanczos"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(webm),
            "-vf",
            f"{filters},palettegen=max_colors=48",
            str(palette),
        ],
        check=True,
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(webm),
            "-i",
            str(palette),
            "-lavfi",
            f"{filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
            "-loop",
            "0",
            str(gif),
        ],
        check=True,
    )
    palette.unlink(missing_ok=True)
    webm.unlink(missing_ok=True)
    print(f"demo.gif {gif.stat().st_size / 1e6:.2f} MB, demo.mp4 {mp4.stat().st_size / 1e6:.2f} MB")


def main() -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("record_demo: playwright is not installed (pip install -e '.[evidence]')")
        return 2
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chdir(REPO)
    segments = capture()
    MANIFEST.write_text(
        json.dumps(
            {
                "note": "every line in demo.gif is captured output from these commands",
                "segments": segments,
            },
            indent=2,
        )
        + "\n"
    )
    build_player(segments)
    webm = record()
    transcode(webm)
    PLAYER.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
