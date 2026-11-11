"""Experiment 4: what the severity policy rests on.

Question the README asks: for each drift class, is the runtime consequence documented by
Salesforce, or inferred from the contract and never observed against an org? This table is
what ADR-003 and ADR-005 are about, and it is the uncomfortable one: most of the classes,
including most of the fatal ones, rest on inference.
"""

from __future__ import annotations

from _common import fixture_report, table, write
from afcl.contracts import DRIFT_CLASSES, FATAL


def main() -> None:
    _, report = fixture_report()
    counts = report.by_class()
    rows = []
    for dc in DRIFT_CLASSES.values():
        rows.append(
            {
                "drift_class": dc.name,
                "severity": dc.severity,
                "evidence": dc.evidence,
                "name_visible": dc.name_visible,
                "fixture_count": counts.get(dc.name, 0),
                "consequence": dc.consequence,
            }
        )
    documented = [r for r in rows if r["evidence"] == "documented"]
    inferred = [r for r in rows if r["evidence"] == "inferred"]
    fatal = [r for r in rows if r["severity"] == FATAL]
    fatal_documented = [r for r in fatal if r["evidence"] == "documented"]

    payload = {
        "classes_total": len(rows),
        "classes_documented": len(documented),
        "classes_inferred": len(inferred),
        "fatal_classes": len(fatal),
        "fatal_documented": len(fatal_documented),
        "fatal_inferred": len(fatal) - len(fatal_documented),
        "fails_by_default": [r["drift_class"] for r in fatal],
        "rows": rows,
        "note": (
            "documented means the GenAiFunction metadata reference states the consequence; "
            "inferred means it follows from the contract and has not been observed against an "
            "org in this repository (ADR-005)"
        ),
    }
    path = write("exp04_severity_evidence", payload)
    print(
        table(
            [[r["drift_class"], r["severity"], r["evidence"], r["fixture_count"]] for r in rows],
            ["drift class", "severity", "evidence", "fixture"],
        )
    )
    print()
    print(
        f"{payload['classes_documented']} of {payload['classes_total']} classes rest on a "
        f"documented consequence; {payload['fatal_inferred']} of {payload['fatal_classes']} "
        "fatal classes are inferred."
    )
    print(f"wrote {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    main()
