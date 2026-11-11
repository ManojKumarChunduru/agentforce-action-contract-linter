"""Properties of the renderers and the command line, including the exit code contract."""

import io
import json
import re
import xml.etree.ElementTree as ET

import pytest

from afcl import exit_codes
from afcl.cli import build_parser, main, run_lint
from afcl.contracts import DRIFT_CLASSES, LintReport
from afcl.report import (
    RENDERERS,
    summary_rows,
    to_dict,
    to_html,
    to_json,
    to_markdown,
    to_text,
    verdict,
)
from tests.conftest import FIXTURE_ROOT, input_schema, output_schema, prop

T, BOOL = "lightning__textType", "lightning__booleanType"


def clean_builder(builder):
    builder.apex("A", [("String", "a")], [("Boolean", "ok")])
    builder.action(
        "Act",
        "A",
        input=input_schema({"a": prop(T)}),
        output=output_schema({"ok": prop(BOOL, planner=True)}),
    )
    builder.topic("T", functions=["Act"])
    return builder


# ---------------------------------------------------------------- renderers


def test_verdict_is_drift_when_the_report_should_fail(fixture_report):
    assert verdict(fixture_report, strict=False) == "DRIFT"


def test_verdict_is_clean_for_an_empty_report():
    assert verdict(LintReport(1, 1, 1), strict=False) == "CLEAN"


def test_verdict_is_clean_with_gaps_when_only_undecidables_remain(builder):
    builder.action("Act", "P", target_type="prompt")
    builder.topic("T", functions=["Act"])
    assert verdict(builder.report(), strict=False) == "CLEAN WITH GAPS"


def test_summary_rows_list_every_class_including_zero_counts():
    rows = summary_rows(LintReport(0, 0, 0))
    assert {r[0] for r in rows} == set(DRIFT_CLASSES) and all(r[3] == 0 for r in rows)


def test_summary_rows_are_ordered_fatal_then_warn_then_info():
    sev = [r[1] for r in summary_rows(LintReport(0, 0, 0))]
    assert sev == sorted(sev, key={"fatal": 0, "warn": 1, "info": 2}.get)


def test_the_json_payload_carries_totals_and_every_finding(fixture_report):
    data = json.loads(to_json(fixture_report))
    assert data["totals"]["actions"] == 17
    assert data["totals"]["findings"] == len(fixture_report.findings)
    assert len(data["findings"]) == len(fixture_report.findings)
    assert all("severity" in f for f in data["findings"])


def test_the_json_findings_are_sorted_fatal_first(fixture_report):
    data = to_dict(fixture_report)
    sevs = [f["severity"] for f in data["findings"]]
    assert sevs == sorted(sevs, key={"fatal": 0, "warn": 1, "info": 2}.get)


def test_the_text_report_names_the_verdict_and_every_finding(fixture_report):
    text = to_text(fixture_report)
    assert text.startswith("agentforce action contract linter: DRIFT")
    for f in fixture_report.findings:
        assert f.action in text


def test_the_text_report_lists_undecidables_apart_from_findings(fixture_report):
    text = to_text(fixture_report)
    assert "undecidable (not checked, not counted as drift)" in text
    assert "Merge_Duplicate_Contacts.primary" in text


def test_the_text_report_for_a_clean_project_has_no_findings_section(builder):
    text = to_text(clean_builder(builder).report())
    assert "findings\n" not in text and "CLEAN" in text


def test_the_markdown_report_is_a_table_per_section(fixture_report):
    md = to_markdown(fixture_report)
    assert md.count("| --- |") >= 3 and "| fatal | missing_target |" in md


def test_the_markdown_report_escapes_pipes_in_messages():
    report = LintReport(0, 0, 0)
    from afcl.contracts import Finding

    report.findings.append(Finding("orphan_input", "Act", "a | b"))
    assert "a \\| b" in to_markdown(report)


def test_the_html_report_is_well_formed_and_has_the_named_headings(fixture_report):
    html = to_html(fixture_report)
    body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    ET.fromstring(f"<root>{body}</root>")
    for heading in ("summary", "findings", "undecidable"):
        assert f"id='{heading}'" in html


def test_every_css_class_used_in_the_html_has_a_rule(fixture_report):
    html = to_html(fixture_report)
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    used = set()
    for m in re.finditer(r"class='([^']+)'", html):
        used.update(m.group(1).split())
    defined = set(re.findall(r"\.([a-z][a-z0-9-]*)", css))
    assert used <= defined, used - defined


def test_the_html_badge_class_follows_the_verdict(builder):
    assert "badge-clean" in to_html(clean_builder(builder).report())


def test_the_html_report_escapes_markup_in_messages():
    from afcl.contracts import Finding

    report = LintReport(0, 0, 0)
    report.findings.append(Finding("orphan_input", "<Act>", "a<b"))
    html = to_html(report)
    assert "&lt;Act&gt;" in html and "a&lt;b" in html and "<Act>" not in html


def test_the_html_report_for_a_clean_project_says_none_twice(builder):
    assert to_html(clean_builder(builder).report()).count("None.") == 2


def test_all_four_renderers_are_registered():
    assert set(RENDERERS) == {"text", "json", "markdown", "html"}


# ---------------------------------------------------------------- cli


def run(argv, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    code = run_lint(build_parser().parse_args(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_the_fixture_exits_1_because_drift_was_found():
    code, out, _ = run(["lint", str(FIXTURE_ROOT)])
    assert code == exit_codes.DRIFT_FOUND and "DRIFT" in out


def test_a_clean_project_exits_0(builder):
    code, out, _ = run(["lint", str(clean_builder(builder).root)])
    assert code == exit_codes.CLEAN and "CLEAN" in out


def test_a_missing_project_exits_2_and_says_why(tmp_path):
    code, _, err = run(["lint", str(tmp_path)])
    assert code == exit_codes.COULD_NOT_ANSWER and "sfdx-project.json" in err


def test_unreadable_files_exit_2_with_no_report_by_default(builder):
    clean_builder(builder).flow("Bad", source="<Flow>")
    code, out, err = run(["lint", str(builder.root)])
    assert code == exit_codes.COULD_NOT_ANSWER and out == "" and "Bad.flow-meta.xml" in err


def test_allow_load_errors_prints_the_report_but_still_exits_2(builder):
    clean_builder(builder).flow("Bad", source="<Flow>")
    code, out, err = run(["lint", str(builder.root), "--allow-load-errors"])
    assert code == exit_codes.COULD_NOT_ANSWER and "CLEAN" in out and "unreadable" in err


def test_strict_turns_a_warn_only_project_into_exit_1(builder):
    builder.apex("A", [("String", "a"), ("String", "b")], [("Boolean", "ok")])
    builder.action(
        "Act",
        "A",
        input=input_schema({"a": prop(T)}),
        output=output_schema({"ok": prop(BOOL, planner=True)}),
    )
    builder.topic("T", functions=["Act"])
    assert run(["lint", str(builder.root)])[0] == exit_codes.CLEAN
    assert run(["lint", str(builder.root), "--strict"])[0] == exit_codes.DRIFT_FOUND


def test_json_format_produces_parseable_json(builder):
    _, out, _ = run(["lint", str(clean_builder(builder).root), "--format", "json"])
    assert json.loads(out)["verdict"] == "CLEAN"


def test_output_writes_the_report_to_a_file_and_prints_the_verdict_to_stderr(builder, tmp_path):
    target = tmp_path / "out" / "report.html"
    code, out, err = run(
        ["lint", str(clean_builder(builder).root), "--format", "html", "--output", str(target)]
    )
    assert code == 0 and out == "" and target.exists() and "CLEAN" in err


def test_classes_subcommand_lists_every_drift_class(capsys):
    assert main(["classes"]) == 0
    out = capsys.readouterr().out
    for name in DRIFT_CLASSES:
        assert name in out


def test_classes_subcommand_renders_markdown(capsys):
    main(["classes", "--format", "markdown"])
    assert capsys.readouterr().out.startswith("| class |")


def test_bad_usage_exits_3(capsys):
    assert main(["lint"]) == exit_codes.USAGE


def test_help_exits_0(capsys):
    assert main(["--help"]) == 0


def test_main_runs_lint_end_to_end(capsys):
    assert main(["lint", str(FIXTURE_ROOT)]) == exit_codes.DRIFT_FOUND


def test_exit_code_descriptions_cover_every_code():
    assert set(exit_codes.DESCRIPTIONS) == {0, 1, 2, 3}


def test_the_parser_defaults_to_text_output():
    assert build_parser().parse_args(["lint", "x"]).format == "text"


@pytest.mark.parametrize("fmt", ["text", "json", "markdown", "html"])
def test_every_format_is_accepted_by_the_parser(fmt):
    assert build_parser().parse_args(["lint", "x", "--format", fmt]).format == fmt


def test_python_dash_m_afcl_is_the_same_entry_point():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "afcl", "lint", str(FIXTURE_ROOT), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == exit_codes.DRIFT_FOUND
    assert json.loads(proc.stdout)["verdict"] == "DRIFT"


def test_a_policy_file_changes_the_exit_code(builder, tmp_path):
    builder.apex("A", [("Id", "a")], [("Boolean", "ok")])
    builder.action(
        "Act",
        "A",
        input=input_schema({"a": prop(T)}),
        output=output_schema({"ok": prop(BOOL, planner=True)}),
    )
    builder.topic("T", functions=["Act"])
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"severity": {"type_mismatch": "fatal"}}))
    assert run(["lint", str(builder.root)])[0] == exit_codes.CLEAN
    assert run(["lint", str(builder.root), "--policy", str(policy)])[0] == exit_codes.DRIFT_FOUND


def test_an_invalid_policy_file_exits_3_before_anything_is_examined(builder, tmp_path):
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"severity": {"nope": "fatal"}}))
    code, out, err = run(["lint", str(clean_builder(builder).root), "--policy", str(policy)])
    assert code == exit_codes.USAGE and out == "" and "unknown drift class" in err


def test_a_missing_or_malformed_policy_file_exits_3(builder, tmp_path):
    code, _, err = run(
        ["lint", str(clean_builder(builder).root), "--policy", str(tmp_path / "none.json")]
    )
    assert code == exit_codes.USAGE and "does not exist" in err
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    code, _, err = run(["lint", str(builder.root), "--policy", str(bad)])
    assert code == exit_codes.USAGE and "not valid JSON" in err


def test_the_policy_subcommand_prints_valid_json_with_every_class(capsys):
    assert main(["policy"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert set(doc["severity"]) == set(DRIFT_CLASSES)


def test_the_json_report_records_the_policy_in_force(builder):
    _, out, _ = run(["lint", str(clean_builder(builder).root), "--format", "json"])
    assert json.loads(out)["policy"] == {"severity_overrides": {}, "fail_on_undecidable": False}
