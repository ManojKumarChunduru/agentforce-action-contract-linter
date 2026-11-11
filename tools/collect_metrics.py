"""Re-measure every published figure and write docs/metrics.json.

Nothing in this file is typed by hand. The test count and coverage come from pytest's machine
readable reports, every other figure comes from an experiment's JSON, and the anchors say the
exact wording a document must use for each value. `check_numbers.py` then holds the documents
to those anchors. If a figure is not produced here, it has no business in the README.

Usage:
    python tools/collect_metrics.py              # runs the suite, then the experiments
    python tools/collect_metrics.py --skip-tests # CI runs pytest as its own step; read its reports
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
EXPERIMENTS = REPO / "docs" / "experiments"
METRICS = REPO / "docs" / "metrics.json"

sys.path.insert(0, str(REPO / "src"))
from afcl.contracts import DRIFT_CLASSES  # noqa: E402
from afcl.schema import TEXT_CAP  # noqa: E402

EXPERIMENT_SCRIPTS = [
    "exp01_drift_census.py",
    "exp02_name_only_review.py",
    "exp03_undecidable.py",
    "exp04_severity_evidence.py",
]

# Anchor phrases: `{}` is the metric's own value, `{name}` is another metric's value. A document
# must contain at least one anchor per metric, and every occurrence of an anchor's stem must carry
# the current value. Keep each to the number and two or three words so it survives line wrapping.
ANCHORS: dict[str, list[str]] = {
    "tests_total": ["{} tests"],
    "coverage_line_pct": ["{}% line coverage"],
    "actions_total": ["{} actions"],
    "topics_total": ["{} topics"],
    "apex_actions": ["{} backed by Apex"],
    "flow_actions": ["{} backed by Flow"],
    "fixture_apex_classes": ["{} Apex classes"],
    "fixture_flows": ["{} Flows"],
    "findings_total": ["{} findings"],
    "actions_with_findings": ["across {} of {actions_total} actions"],
    "contract_drifted_actions": ["{} with contract drift"],
    "clean_actions": ["{} clean actions", "{} are clean"],
    "drift_classes_total": ["{} drift classes"],
    "type_mismatch_count": ["{} type mismatches"],
    "planted_drifts": ["{} planted drifts", "floor of 1/{}", "1/{} on this fixture"],
    "ground_truth_matched": ["{} of {planted_drifts} planted"],
    "name_only_visible": ["review sees {}", "sees {} of {findings_total}"],
    "name_only_invisible": ["{} of {findings_total} findings", "misses {}", "{} invisible"],
    "name_only_invisible_pct": ["{}% of the findings", "({}%) are invisible"],
    "matched_pairs": ["{} matched pairs", "of {matched_pairs} pairs"],
    "undecidable_properties": ["{} undecidable properties", "{} properties it cannot"],
    "undecidable_actions": [
        "{} of {actions_total} actions are undecidable",
        "{} undecidable actions",
    ],
    "undecidable_actions_pct": ["{}% of actions", "({}%) are undecidable"],
    "undecidable_pairs_pct": ["{}% of matched pairs"],
    "classes_documented": ["{} of {drift_classes_total} classes", "{} documented classes"],
    "classes_inferred": ["{} inferred classes", "{} are inferred"],
    "fatal_classes": ["{} fatal classes", "of {fatal_classes} fatal"],
    "fatal_inferred": ["{} of {fatal_classes} fatal"],
    "fatal_documented": ["{} fatal class rests", "only {} of the fatal"],
    "text_cap": ["cap of {}", "{} characters"],
}


def run_tests() -> None:
    REPORTS.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        f"--junitxml={REPORTS / 'junit.xml'}",
        "--cov=afcl",
        "--cov-branch",
        f"--cov-report=json:{REPORTS / 'coverage.json'}",
    ]
    subprocess.run(cmd, cwd=REPO, check=True)


def read_test_reports() -> tuple[int, float]:
    junit = ET.parse(REPORTS / "junit.xml").getroot()
    suites = junit.findall("testsuite") if junit.tag == "testsuites" else [junit]
    total = sum(int(s.get("tests", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    failures = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    if failures:
        raise SystemExit(f"junit reports {failures} failing tests; refusing to publish metrics")
    cov = json.loads((REPORTS / "coverage.json").read_text())
    totals = cov["totals"]
    line_pct = round(100.0 * totals["covered_lines"] / totals["num_statements"], 1)
    return total - skipped, line_pct


def run_experiments() -> dict[str, dict]:
    out = {}
    for script in EXPERIMENT_SCRIPTS:
        subprocess.run(
            [sys.executable, str(REPO / "experiments" / script)],
            cwd=REPO,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        name = script.removesuffix(".py")
        out[name] = json.loads((EXPERIMENTS / f"{name}.json").read_text())
    return out


def count_fixture_sources() -> tuple[int, int]:
    default = REPO / "fixture" / "force-app" / "main" / "default"
    return len(list(default.glob("classes/*.cls"))), len(
        list(default.glob("flows/*.flow-meta.xml"))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-tests", action="store_true", help="read reports/ instead of running pytest"
    )
    args = parser.parse_args()
    if not args.skip_tests:
        run_tests()
    tests_total, coverage = read_test_reports()
    exp = run_experiments()
    e1, e2, e3, e4 = (
        exp["exp01_drift_census"],
        exp["exp02_name_only_review"],
        exp["exp03_undecidable"],
        exp["exp04_severity_evidence"],
    )
    apex_classes, flows = count_fixture_sources()

    metrics = {
        "tests_total": tests_total,
        "coverage_line_pct": coverage,
        "actions_total": e1["actions_total"],
        "topics_total": e1["topics_total"],
        "apex_actions": e1["apex_actions"],
        "flow_actions": e1["flow_actions"],
        "fixture_apex_classes": apex_classes,
        "fixture_flows": flows,
        "findings_total": e1["findings_total"],
        "actions_with_findings": e1["actions_with_findings"],
        "contract_drifted_actions": e1["contract_drifted_actions"],
        "clean_actions": e1["clean_actions"],
        "drift_classes_total": len(DRIFT_CLASSES),
        "type_mismatch_count": e1["by_class"].get("type_mismatch", 0),
        "planted_drifts": e1["ground_truth"]["planted"],
        "ground_truth_matched": e1["ground_truth"]["true_positive"],
        "name_only_visible": e2["findings_name_only"],
        "name_only_invisible": e2["invisible_to_name_only"],
        "name_only_invisible_pct": e2["invisible_share_pct"],
        "matched_pairs": e3["matched_pairs"],
        "undecidable_properties": e3["undecidable_properties"],
        "undecidable_actions": e3["undecidable_actions"],
        "undecidable_actions_pct": e3["undecidable_share_of_actions_pct"],
        "undecidable_pairs_pct": e3["undecidable_share_of_matched_pairs_pct"],
        "classes_documented": e4["classes_documented"],
        "classes_inferred": e4["classes_inferred"],
        "fatal_classes": e4["fatal_classes"],
        "fatal_inferred": e4["fatal_inferred"],
        "fatal_documented": e4["fatal_documented"],
        "text_cap": TEXT_CAP,
    }
    missing_anchor = [k for k in metrics if k not in ANCHORS]
    if missing_anchor:
        raise SystemExit(f"metrics with no anchor phrase: {missing_anchor}")
    payload = {
        "metrics": metrics,
        "anchors": ANCHORS,
        "checked_documents": [
            "README.md",
            "docs/defense-guide.md",
            "fixture/README.md",
            *sorted(str(p.relative_to(REPO)) for p in (REPO / "docs" / "adr").glob("*.md")),
        ],
        "note": "every value here is produced by running the suite and the experiments",
    }
    METRICS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for k, v in metrics.items():
        print(f"{k:<28} {v}")
    print(f"wrote {METRICS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
