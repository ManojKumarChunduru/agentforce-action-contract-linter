"""Experiment 2: what a name-only review misses.

Question the README asks: if a careful reviewer reconciles schema properties against invocable
variables by name alone, which is what a pull request review actually does, how many of the
fixture's drifts are invisible to that review? This is the number ADR-001 rests on.
"""

from __future__ import annotations

from _common import fixture_report, table, write


def main() -> None:
    _, full = fixture_report()
    _, name_only = fixture_report(name_only=True)

    key = lambda f: (f.drift_class, f.action, f.property_name)  # noqa: E731
    seen = {key(f) for f in name_only.findings}
    invisible = [f for f in full.findings if key(f) not in seen]
    by_class = {}
    for f in invisible:
        by_class[f.drift_class] = by_class.get(f.drift_class, 0) + 1

    payload = {
        "findings_full": len(full.findings),
        "findings_name_only": len(name_only.findings),
        "invisible_to_name_only": len(invisible),
        "invisible_share_pct": round(100 * len(invisible) / len(full.findings), 1),
        "invisible_by_class": dict(sorted(by_class.items())),
        "invisible_findings": [
            {"drift_class": f.drift_class, "action": f.action, "property": f.property_name}
            for f in invisible
        ],
        "note": (
            "name-only reconciliation matches property names in both directions and nothing "
            "else; it sees missing targets, orphans, uncovered inputs, dangling topic functions "
            "and unreachable actions, and cannot see types, required-ness, caps, planner flags "
            "or Flow status"
        ),
    }
    path = write("exp02_name_only_review", payload)
    rows = [[k, v] for k, v in payload["invisible_by_class"].items()]
    print(table(rows, ["invisible to a name-only review", "count"]))
    print()
    print(
        f"name-only review sees {payload['findings_name_only']} of {payload['findings_full']} "
        f"findings; {payload['invisible_to_name_only']} ({payload['invisible_share_pct']}%) are "
        "invisible to it."
    )
    print(f"wrote {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    main()
