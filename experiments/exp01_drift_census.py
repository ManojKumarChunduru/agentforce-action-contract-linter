"""Experiment 1: the drift census.

Question the README asks: across a fixture org with every drift class planted once, what does
the linter report, by class, by severity and by target language, and does it match the ground
truth exactly? The last part is the fixture's own limit: a planted corpus can show the linter
finds what was planted and nothing else, and the resolution floor says how little that proves
about a real org.
"""

from __future__ import annotations

import json
from collections import Counter

from _common import FIXTURE, fixture_report, table, write


def main() -> None:
    project, report = fixture_report()
    expected = json.loads((FIXTURE / "EXPECTED_DRIFTS.json").read_text())

    got = sorted((f.drift_class, f.action, f.property_name) for f in report.findings)
    want = sorted((e["drift_class"], e["action"], e["property_name"]) for e in expected["findings"])
    true_positive = len([g for g in got if g in want])
    false_positive = len(got) - true_positive
    false_negative = len(want) - true_positive

    contract_findings = [f for f in report.findings if f.drift_class != "unreachable_action"]
    contract_actions = {
        f.action for f in contract_findings if f.drift_class != "dangling_topic_function"
    }
    by_target = Counter(f.target_type or "none" for f in report.findings)
    apex_actions = sum(1 for a in project.actions.values() if a.invocation_target_type == "apex")
    flow_actions = sum(1 for a in project.actions.values() if a.invocation_target_type == "flow")

    payload = {
        "actions_total": report.actions_total,
        "topics_total": report.topics_total,
        "planners_total": report.planners_total,
        "apex_actions": apex_actions,
        "flow_actions": flow_actions,
        "findings_total": len(report.findings),
        "actions_with_findings": len(report.actions_with_findings()),
        "contract_drifted_actions": len(contract_actions),
        "clean_actions": len(expected["clean_actions"]),
        "by_class": dict(sorted(report.by_class().items())),
        "by_severity": dict(sorted(report.by_severity().items())),
        "by_target_type": dict(sorted(by_target.items())),
        "ground_truth": {
            "planted": len(want),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "resolution_floor": round(1 / len(want), 4),
            "note": (
                "a planted fixture can only show the linter finds what was planted; a measured "
                "zero false positives over N planted drifts means a rate below 1/N, not zero"
            ),
        },
    }
    path = write("exp01_drift_census", payload)
    rows = [[k, v] for k, v in payload["by_class"].items()]
    print(table(rows, ["drift class", "count"]))
    print()
    print(
        f"{payload['findings_total']} findings across {payload['actions_with_findings']} of "
        f"{payload['actions_total']} actions; {payload['contract_drifted_actions']} with contract "
        f"drift, {payload['clean_actions']} clean. Ground truth: {true_positive}/{len(want)} "
        f"matched, {false_positive} extra, resolution floor 1/{len(want)}."
    )
    print(f"wrote {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    main()
