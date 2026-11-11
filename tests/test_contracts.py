"""Properties of the reconciliation: one drift at a time, then the fixture against ground truth."""

from afcl.contracts import DRIFT_CLASSES, FATAL, INFO, WARN, reconcile
from tests.conftest import input_schema, output_schema, prop

T, RID, INT, NUM, BOOL = (
    "lightning__textType",
    "lightning__recordIdType",
    "lightning__integerType",
    "lightning__numberType",
    "lightning__booleanType",
)


def clean_output():
    return output_schema({"ok": prop(BOOL, planner=True)})


def only(report, drift_class):
    found = [f for f in report.findings if f.drift_class == drift_class]
    assert len(found) == 1, [f.drift_class for f in report.findings]
    return found[0]


def classes(report):
    return sorted(f.drift_class for f in report.findings)


def reachable(builder, *actions):
    builder.topic("T", functions=list(actions))


# ---------------------------------------------------------------- clean


def test_a_fully_matched_apex_action_has_no_findings(builder):
    builder.apex("A", [("String", "a", True)], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}, ["a"]), output=clean_output())
    reachable(builder, "Act")
    report = builder.report()
    assert report.findings == [] and report.undecidables == []


def test_a_fully_matched_flow_action_has_no_findings(builder):
    builder.flow("F", [("String", "a")], [("Boolean", "ok")])
    builder.action("Act", "F", "flow", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    assert builder.report().findings == []


def test_a_label_that_differs_from_the_title_is_not_a_drift(builder):
    src = """
    public class A {
        public class Request { @InvocableVariable(label='Case Number') public String caseNumber; }
        public class Response { @InvocableVariable public Boolean ok; }
        @InvocableMethod
        public static List<Response> run(List<Request> r) { return null; }
    }"""
    builder.apex("A", source=src)
    builder.action(
        "Act",
        "A",
        input=input_schema({"caseNumber": prop(T, title="Case record number")}),
        output=clean_output(),
    )
    reachable(builder, "Act")
    assert builder.report().findings == []


# ---------------------------------------------------------------- one drift at a time


def test_a_target_not_in_the_project_is_missing_target(builder):
    builder.action("Act", "Ghost", input=input_schema({}), output=clean_output())
    reachable(builder, "Act")
    f = only(builder.report(), "missing_target")
    assert f.detail == "not in project" and f.severity == FATAL


def test_a_class_without_an_invocable_method_is_missing_target(builder):
    builder.apex("Helper", source="public class Helper { public static void f() {} }")
    builder.action("Act", "Helper", output=clean_output())
    reachable(builder, "Act")
    assert only(builder.report(), "missing_target").detail == "class has no @InvocableMethod"


def test_a_missing_target_stops_further_checks_on_that_action(builder):
    builder.action("Act", "Ghost", input=input_schema({"a": prop(T)}))
    reachable(builder, "Act")
    assert classes(builder.report()) == ["missing_target"]


def test_a_draft_flow_is_target_inactive(builder):
    builder.flow("F", [], [("Boolean", "ok")], status="Draft")
    builder.action("Act", "F", "flow", output=clean_output())
    reachable(builder, "Act")
    assert only(builder.report(), "target_inactive").severity == FATAL


def test_an_output_schema_with_no_planner_usable_property_is_no_planner_output(builder):
    builder.apex("A", [], [("Boolean", "ok")])
    builder.action("Act", "A", output=output_schema({"ok": prop(BOOL)}))
    reachable(builder, "Act")
    f = only(builder.report(), "no_planner_output")
    assert f.severity == FATAL and DRIFT_CLASSES[f.drift_class].evidence == "documented"


def test_an_action_with_no_output_schema_at_all_is_no_planner_output(builder):
    builder.apex("A", [], [("Boolean", "ok")])
    builder.action("Act", "A")
    reachable(builder, "Act")
    assert classes(builder.report()) == ["no_planner_output"]


def test_a_schema_input_with_no_target_variable_is_orphan_input(builder):
    builder.apex("A", [("String", "a")], [("Boolean", "ok")])
    builder.action(
        "Act", "A", input=input_schema({"a": prop(T), "extra": prop(BOOL)}), output=clean_output()
    )
    reachable(builder, "Act")
    f = only(builder.report(), "orphan_input")
    assert f.property_name == "extra" and f.severity == WARN


def test_an_optional_target_input_absent_from_the_schema_is_uncovered_input(builder):
    builder.apex("A", [("String", "a"), ("String", "b")], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    assert only(builder.report(), "uncovered_input").property_name == "b"


def test_a_required_target_input_absent_from_the_schema_is_missing_required_input(builder):
    builder.apex("A", [("String", "a"), ("String", "b", True)], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    f = only(builder.report(), "missing_required_input")
    assert f.property_name == "b" and f.detail == "absent"


def test_a_required_target_input_that_is_optional_in_the_schema_is_missing_required_input(builder):
    builder.apex("A", [("String", "a", True)], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    assert only(builder.report(), "missing_required_input").detail == "optional_in_schema"


def test_an_action_with_no_input_schema_reports_every_target_input_as_uncovered(builder):
    builder.apex("A", [("String", "a"), ("String", "b", True)], [("Boolean", "ok")])
    builder.action("Act", "A", output=clean_output())
    reachable(builder, "Act")
    assert classes(builder.report()) == ["missing_required_input", "uncovered_input"]


def test_an_id_declared_as_text_is_an_input_type_mismatch(builder):
    builder.apex("A", [("Id", "a")], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    f = only(builder.report(), "type_mismatch")
    assert f.detail.startswith("weakened") and f.property_name == "a"


def test_an_output_type_disagreement_is_an_output_type_mismatch(builder):
    builder.apex("A", [], [("Integer", "n")])
    builder.action("Act", "A", output=output_schema({"n": prop(NUM, planner=True)}))
    reachable(builder, "Act")
    assert only(builder.report(), "type_mismatch").message.startswith("output")


def test_a_schema_output_the_target_never_produces_is_orphan_output(builder):
    builder.apex("A", [], [("Boolean", "ok")])
    builder.action(
        "Act", "A", output=output_schema({"ok": prop(BOOL, planner=True), "ghost": prop(T)})
    )
    reachable(builder, "Act")
    assert only(builder.report(), "orphan_output").property_name == "ghost"


def test_a_target_output_the_schema_does_not_expose_is_not_a_finding(builder):
    builder.apex("A", [], [("Boolean", "ok"), ("String", "internal")])
    builder.action("Act", "A", output=clean_output())
    reachable(builder, "Act")
    assert builder.report().findings == []


def test_an_input_text_above_the_cap_is_text_cap_exceeded(builder):
    builder.apex("A", [("String", "a")], [("Boolean", "ok")])
    builder.action(
        "Act", "A", input=input_schema({"a": prop(T, maxLength=251)}), output=clean_output()
    )
    reachable(builder, "Act")
    assert only(builder.report(), "text_cap_exceeded").detail == "251"


def test_an_output_text_above_the_cap_is_text_cap_exceeded(builder):
    builder.apex("A", [], [("String", "s")])
    builder.action("Act", "A", output=output_schema({"s": prop(T, planner=True, maxLength=9999)}))
    reachable(builder, "Act")
    assert only(builder.report(), "text_cap_exceeded").message.startswith("output")


def test_an_action_no_topic_lists_is_unreachable_and_only_info(builder):
    builder.apex("A", [], [("Boolean", "ok")])
    builder.action("Act", "A", output=clean_output())
    f = only(builder.report(), "unreachable_action")
    assert f.severity == INFO


def test_a_topic_naming_a_nonexistent_action_is_dangling_topic_function(builder):
    builder.topic("T", functions=["Nope"])
    f = only(builder.report(), "dangling_topic_function")
    assert f.action == "Nope" and f.target == "T" and f.severity == FATAL


def test_a_dangling_function_does_not_count_as_an_action_with_findings(builder):
    builder.topic("T", functions=["Nope"])
    assert builder.report().actions_with_findings() == set()


# ---------------------------------------------------------------- undecidable


def test_an_sobject_input_is_undecidable_not_a_finding(builder):
    src = """
    public class A {
        public class Request { @InvocableVariable public Contact c; }
        public class Response { @InvocableVariable public Boolean ok; }
        @InvocableMethod
        public static List<Response> run(List<Request> r) { return null; }
    }"""
    builder.apex("A", source=src)
    builder.action("Act", "A", input=input_schema({"c": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    report = builder.report()
    assert report.findings == [] and [u.variable for u in report.undecidables] == ["c"]


def test_an_undecidable_output_is_recorded_on_the_output_side(builder):
    src = """
    public class A {
        public class Request { }
        public class Response {
            @InvocableVariable public Account acct;
            @InvocableVariable public Boolean ok;
        }
        @InvocableMethod
        public static List<Response> run(List<Request> r) { return null; }
    }"""
    builder.apex("A", source=src)
    builder.action(
        "Act", "A", output=output_schema({"acct": prop(T), "ok": prop(BOOL, planner=True)})
    )
    reachable(builder, "Act")
    assert builder.report().undecidables[0].side == "output"


def test_an_unsupported_target_type_is_undecidable_at_action_level(builder):
    builder.action("Act", "Prompt_X", target_type="generatePromptResponse")
    reachable(builder, "Act")
    report = builder.report()
    assert report.findings == []
    assert report.undecidables[0].side == "action" and "subset" in report.undecidables[0].reason


# ---------------------------------------------------------------- severity and failure


def test_warn_findings_do_not_fail_by_default_but_do_under_strict(builder):
    builder.apex("A", [("String", "a"), ("String", "b")], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    report = builder.report()
    assert not report.should_fail() and report.should_fail(strict=True)


def test_fatal_findings_fail_by_default(builder):
    builder.action("Act", "Ghost")
    reachable(builder, "Act")
    assert builder.report().should_fail()


def test_undecidable_alone_fails_only_under_strict(builder):
    builder.action("Act", "P", target_type="prompt")
    reachable(builder, "Act")
    report = builder.report()
    assert not report.should_fail() and report.should_fail(strict=True)


def test_info_findings_never_fail_even_under_strict(builder):
    builder.apex("A", [], [("Boolean", "ok")])
    builder.action("Act", "A", output=clean_output())
    report = builder.report()
    assert classes(report) == ["unreachable_action"] and not report.should_fail(strict=True)


def test_every_drift_class_has_a_severity_and_an_evidence_level():
    for dc in DRIFT_CLASSES.values():
        assert dc.severity in (FATAL, WARN, INFO) and dc.evidence in ("documented", "inferred")


def test_exactly_two_drift_classes_rest_on_documented_consequences():
    documented = [dc.name for dc in DRIFT_CLASSES.values() if dc.evidence == "documented"]
    assert sorted(documented) == ["no_planner_output", "text_cap_exceeded"]


# ---------------------------------------------------------------- name-only mode


def test_name_only_mode_still_sees_name_level_drift(builder):
    builder.apex("A", [("String", "a")], [("Boolean", "ok")])
    builder.action(
        "Act", "A", input=input_schema({"a": prop(T), "x": prop(T)}), output=clean_output()
    )
    reachable(builder, "Act")
    assert classes(builder.report(name_only=True)) == ["orphan_input"]


def test_name_only_mode_cannot_see_a_type_mismatch(builder):
    builder.apex("A", [("Id", "a")], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop(T)}), output=clean_output())
    reachable(builder, "Act")
    assert classes(builder.report()) == ["type_mismatch"]
    assert classes(builder.report(name_only=True)) == []


def test_name_only_mode_cannot_see_a_missing_planner_flag(builder):
    builder.apex("A", [], [("Boolean", "ok")])
    builder.action("Act", "A", output=output_schema({"ok": prop(BOOL)}))
    reachable(builder, "Act")
    assert classes(builder.report(name_only=True)) == []


# ---------------------------------------------------------------- the fixture against ground truth


def test_the_fixture_totals_match_the_ground_truth(fixture_report, expected):
    assert fixture_report.actions_total == expected["actions_total"]
    assert fixture_report.topics_total == expected["topics_total"]
    assert fixture_report.planners_total == expected["planners_total"]


def test_the_fixture_findings_equal_the_planted_set_exactly(fixture_report, expected):
    got = sorted((f.drift_class, f.action, f.property_name) for f in fixture_report.findings)
    want = sorted((e["drift_class"], e["action"], e["property_name"]) for e in expected["findings"])
    assert got == want


def test_every_planted_detail_prefix_is_reproduced(fixture_report, expected):
    by_key = {(f.drift_class, f.action, f.property_name): f for f in fixture_report.findings}
    for e in expected["findings"]:
        f = by_key[(e["drift_class"], e["action"], e["property_name"])]
        assert f.detail.startswith(e["detail_prefix"]), (e, f.detail)


def test_the_fixture_undecidables_equal_the_planted_set_exactly(fixture_report, expected):
    got = sorted(
        (u.action, u.variable, u.side, u.declared_type) for u in fixture_report.undecidables
    )
    want = sorted(
        (u["action"], u["variable"], u["side"], u["declared_type"]) for u in expected["undecidable"]
    )
    assert got == want


def test_the_clean_fixture_actions_have_no_findings_and_nothing_undecidable(
    fixture_report, expected
):
    touched = fixture_report.actions_with_findings() | fixture_report.actions_undecidable()
    for name in expected["clean_actions"]:
        assert name not in touched


def test_every_drift_class_appears_at_least_once_in_the_fixture(fixture_report):
    assert set(fixture_report.by_class()) == set(DRIFT_CLASSES)


def test_the_decoy_is_not_reported(fixture_report, expected):
    for decoy in expected["decoys"]:
        assert decoy["action"] not in fixture_report.actions_with_findings()


def test_the_fixture_fails_by_default_because_it_has_fatal_findings(fixture_report):
    assert fixture_report.should_fail() and fixture_report.by_severity()[FATAL] == 4


def test_reconcile_is_pure_and_repeatable(fixture_project):
    a = reconcile(fixture_project)
    b = reconcile(fixture_project)
    assert a.findings == b.findings and a.undecidables == b.undecidables
