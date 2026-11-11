"""Fail the build when a document quotes a figure the code no longer produces.

Three checks, each learned from a way a README goes stale:

1. Presence: every metric in docs/metrics.json must appear in README.md through at least one of
   its anchor phrases with the current value. A metric nobody quotes is a metric nobody checks.
2. Stale anchors: wherever an anchor's stem appears in any checked document ("N findings",
   "across N of 17 actions"), N must be the current value. This is the check that matters: it
   catches "12 findings" after the code started reporting 13, which a digit search would miss
   because 12 is also the number of actions with findings.
3. The reverse scan: any number of 6 or more in a checked document's prose that equals no
   metric value is reported as unguarded, because nothing re-measures it. Fenced code, inline
   code and HTML attributes are excluded, so an example invocation may contain any number it
   likes. Numbers below 6 are too common to mean anything and are checked only through anchors.

Anchors match phrases rather than digits because a digit search passes while the sentence
around it has gone stale. Documents are whitespace-normalised before matching so an anchor that
straddles a wrapped line still matches.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
METRICS = REPO / "docs" / "metrics.json"

NUMBER = r"(\d+(?:\.\d+)?)"
# numbers that are never metrics: Python versions, ADR and experiment numbers, years, semver
IGNORE = [
    re.compile(r"\b3\.1[0-9]\b"),
    re.compile(r"ADR-\d+"),
    re.compile(r"exp\d+"),
    re.compile(r"\b20\d\d\b"),
    re.compile(r"\bv?\d+\.\d+\.\d+\b"),
    re.compile(r"\b\d+px\b"),
    re.compile(r"#\d+"),
]


def normalise(text: str) -> str:
    """Drop fenced code, inline code and HTML tags, then collapse whitespace."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", " ", text)


def same(a: str, b: float | int) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def anchor_regex(anchor: str, metrics: dict) -> re.Pattern:
    """Turn '{} of {actions_total} actions' into a regex with one group for the metric's value."""
    parts = re.split(r"(\{[a-z_]*\})", anchor)
    out = []
    for part in parts:
        if part == "{}":
            out.append(NUMBER)
        elif part.startswith("{") and part.endswith("}"):
            out.append(re.escape(str(metrics[part[1:-1]])))
        else:
            out.append(re.escape(part))
    return re.compile("".join(out))


def main() -> int:
    payload = json.loads(METRICS.read_text())
    metrics: dict = payload["metrics"]
    anchors: dict[str, list[str]] = payload["anchors"]
    docs = {
        d: normalise((REPO / d).read_text(encoding="utf-8")) for d in payload["checked_documents"]
    }
    failures: list[str] = []
    gaps: list[str] = []

    # 1. presence in the README, and 2. stale anchors anywhere
    readme = docs["README.md"]
    for name, value in metrics.items():
        phrases = anchors.get(name, [])
        if not phrases:
            gaps.append(f"{name}={value} has no anchor phrase")
            continue
        patterns = [anchor_regex(a, metrics) for a in phrases]
        present = any(same(m.group(1), value) for p in patterns for m in p.finditer(readme))
        if not present:
            failures.append(f"README does not state {name}={value} through any of {phrases}")
        for doc, text in docs.items():
            for p in patterns:
                for m in p.finditer(text):
                    if not same(m.group(1), value):
                        failures.append(f"{doc}: '{m.group(0)}' is stale; {name} is now {value}")

    # 3. the reverse scan: unguarded numbers
    values = {float(v) for v in metrics.values()}
    for doc, text in docs.items():
        scrubbed = text
        for pat in IGNORE:
            scrubbed = pat.sub(" ", scrubbed)
        for m in re.finditer(r"(?<![\w.\-/])(\d+(?:\.\d+)?)(?![\w.\-/])", scrubbed):
            number = float(m.group(1))
            if number < 6 or number in values:
                continue
            start = max(0, m.start() - 30)
            context = scrubbed[start : m.end() + 30].strip()
            failures.append(f"{doc}: unguarded number {m.group(1)} in '...{context}...'")

    for g in gaps:
        print(f"gap: {g}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"{len(failures)} receipt failure(s)")
        return 1
    print(f"receipts ok: {len(metrics)} metrics checked across {len(docs)} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
