"""Shared plumbing for the experiments: load the fixture once, write JSON where receipts look."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "fixture"
OUT = REPO / "docs" / "experiments"

sys.path.insert(0, str(REPO / "src"))

from afcl.contracts import reconcile  # noqa: E402
from afcl.project import load_project  # noqa: E402


def fixture_report(name_only: bool = False):
    project = load_project(FIXTURE)
    if project.load_errors:
        raise SystemExit(f"fixture has load errors: {project.load_errors}")
    return project, reconcile(project, name_only=name_only)


def write(name: str, payload: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def table(rows: list[list], headers: list[str]) -> str:
    widths = [max(len(str(c)) for c in col) for col in zip(headers, *rows, strict=False)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    lines += [fmt.format(*[str(c) for c in r]) for r in rows]
    return "\n".join(lines)
