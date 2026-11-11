"""Experiment 3: the linter's own blind spot.

Question the README asks: how much of the fixture can the linter not check at all? Every
property it pairs with a target variable it either checks or refuses; this experiment counts the
refusals, says why each happened, and expresses them as a share of the pairs the linter
attempted. A clean verdict is only as good as this number is small.
"""

from __future__ import annotations

from collections import Counter

from _common import fixture_report, table, write


def main() -> None:
    project, report = fixture_report()

    schema_properties = 0
    matched_pairs = 0
    for action in project.actions.values():
        target = project.target_for(action)
        for schema, side in ((action.input_schema, "inputs"), (action.output_schema, "outputs")):
            if schema is None:
                continue
            schema_properties += len(schema.properties)
            if target is None:
                continue
            names = {v.name for v in getattr(target, side)}
            matched_pairs += sum(1 for p in schema.properties if p.name in names)

    reasons = Counter(u.reason.split(";")[0] for u in report.undecidables)
    by_target_type = Counter(u.target_type for u in report.undecidables)

    payload = {
        "schema_properties_total": schema_properties,
        "matched_pairs": matched_pairs,
        "undecidable_properties": len(report.undecidables),
        "undecidable_actions": len(report.actions_undecidable()),
        "actions_total": report.actions_total,
        "undecidable_share_of_matched_pairs_pct": round(
            100 * len(report.undecidables) / matched_pairs, 1
        ),
        "undecidable_share_of_actions_pct": round(
            100 * len(report.actions_undecidable()) / report.actions_total, 1
        ),
        "by_reason": dict(reasons),
        "by_target_type": dict(by_target_type),
        "items": [
            {
                "action": u.action,
                "variable": u.variable,
                "side": u.side,
                "declared_type": u.declared_type,
                "reason": u.reason,
            }
            for u in report.undecidables
        ],
        "note": (
            "undecidable is not drift and not clean; it is a pair the linter refused to judge "
            "because no lightning:type can carry the target's type, so nothing in the schema "
            "could be right or wrong about it"
        ),
    }
    path = write("exp03_undecidable", payload)
    rows = [[i["action"], i["variable"], i["declared_type"], i["reason"]] for i in payload["items"]]
    print(table(rows, ["action", "variable", "declared type", "reason"]))
    print()
    print(
        f"{payload['undecidable_properties']} of {matched_pairs} matched pairs "
        f"({payload['undecidable_share_of_matched_pairs_pct']}%) and "
        f"{payload['undecidable_actions']} of {report.actions_total} actions "
        f"({payload['undecidable_share_of_actions_pct']}%) are undecidable."
    )
    print(f"wrote {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    main()
