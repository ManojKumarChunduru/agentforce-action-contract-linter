"""Properties of topic parsing, planner bundles and project loading."""

import json

import pytest

from afcl.project import ProjectError, load_project, package_directories
from afcl.topics import TopicError, parse_planner_bundle, parse_topic, reachable_actions
from tests.conftest import NS, input_schema, output_schema, prop

# ---------------------------------------------------------------- topics


def test_a_topic_lists_its_functions_in_order(builder):
    p = builder.topic("T", functions=["A", "B"])
    assert parse_topic(p).functions == ["A", "B"]


def test_a_topic_counts_its_instructions(builder):
    p = builder.topic("T", instructions=3)
    assert parse_topic(p).instruction_count == 3


def test_a_topic_without_a_developer_name_falls_back_to_the_file_name(tmp_path):
    p = tmp_path / "Fallback.genAiPlugin-meta.xml"
    p.write_text(
        f'<?xml version="1.0"?><GenAiPlugin {NS}><masterLabel>x</masterLabel></GenAiPlugin>'
    )
    assert parse_topic(p).name == "Fallback"


def test_can_escalate_is_read(tmp_path):
    p = tmp_path / "T.genAiPlugin-meta.xml"
    p.write_text(
        f'<?xml version="1.0"?><GenAiPlugin {NS}><canEscalate>true</canEscalate></GenAiPlugin>'
    )
    assert parse_topic(p).can_escalate is True


def test_a_function_entry_with_no_name_is_skipped(tmp_path):
    p = tmp_path / "T.genAiPlugin-meta.xml"
    p.write_text(
        f'<?xml version="1.0"?><GenAiPlugin {NS}><genAiFunctions></genAiFunctions>'
        "<genAiFunctions><functionName>A</functionName></genAiFunctions></GenAiPlugin>"
    )
    assert parse_topic(p).functions == ["A"]


def test_malformed_topic_xml_is_a_topic_error(tmp_path):
    p = tmp_path / "T.genAiPlugin-meta.xml"
    p.write_text("<GenAiPlugin>")
    with pytest.raises(TopicError, match="well-formed"):
        parse_topic(p)


def test_a_topic_file_with_the_wrong_root_is_a_topic_error(tmp_path):
    p = tmp_path / "T.genAiPlugin-meta.xml"
    p.write_text(f'<?xml version="1.0"?><Flow {NS}></Flow>')
    with pytest.raises(TopicError, match="not GenAiPlugin"):
        parse_topic(p)


def test_a_planner_bundle_lists_its_topics(builder):
    p = builder.planner("Agent", topics=["T1", "T2"])
    bundle = parse_planner_bundle(p)
    assert bundle.topics == ["T1", "T2"] and bundle.name == "Agent"


def test_a_planner_entry_with_no_name_is_skipped(tmp_path):
    p = tmp_path / "A.genAiPlannerBundle-meta.xml"
    p.write_text(
        f'<?xml version="1.0"?><GenAiPlannerBundle {NS}><genAiPlugins></genAiPlugins>'
        "</GenAiPlannerBundle>"
    )
    assert parse_planner_bundle(p).topics == []


def test_reachable_actions_is_the_union_over_topics(builder):
    builder.topic("T1", functions=["A", "B"])
    builder.topic("T2", functions=["B", "C"])
    assert reachable_actions(builder.load().topics) == {"A", "B", "C"}


# ---------------------------------------------------------------- project


def test_a_directory_without_sfdx_project_json_is_a_project_error(tmp_path):
    with pytest.raises(ProjectError, match="sfdx-project.json"):
        load_project(tmp_path)


def test_invalid_sfdx_project_json_is_a_project_error(tmp_path):
    (tmp_path / "sfdx-project.json").write_text("{not json")
    with pytest.raises(ProjectError, match="not valid JSON"):
        package_directories(tmp_path)


def test_missing_package_directories_is_a_project_error(tmp_path):
    (tmp_path / "sfdx-project.json").write_text(json.dumps({"name": "x"}))
    with pytest.raises(ProjectError, match="packageDirectories"):
        package_directories(tmp_path)


def test_a_package_entry_without_a_path_is_a_project_error(tmp_path):
    (tmp_path / "sfdx-project.json").write_text(json.dumps({"packageDirectories": [{}]}))
    with pytest.raises(ProjectError, match="needs a path"):
        package_directories(tmp_path)


def test_a_package_directory_that_does_not_exist_is_a_project_error(tmp_path):
    (tmp_path / "sfdx-project.json").write_text(
        json.dumps({"packageDirectories": [{"path": "nowhere"}]})
    )
    with pytest.raises(ProjectError, match="does not exist"):
        package_directories(tmp_path)


def test_every_piece_is_indexed_by_name(builder):
    builder.apex("A", [("String", "a")], [("Boolean", "ok")])
    builder.flow("F", [("String", "a")], [("Boolean", "ok")])
    builder.action("Act", "A", input=input_schema({"a": prop("lightning__textType")}))
    builder.topic("T", functions=["Act"])
    builder.planner("P", topics=["T"])
    project = builder.load()
    assert set(project.apex_targets) == {"A"}
    assert set(project.flow_targets) == {"F"}
    assert set(project.actions) == {"Act"}
    assert set(project.topics) == {"T"}
    assert set(project.planners) == {"P"}
    assert project.load_errors == []


def test_an_action_folder_without_meta_xml_is_a_load_error(builder):
    builder.write("genAiFunctions/Broken/input/schema.json", "{}")
    project = builder.load()
    assert project.actions == {} and "no -meta.xml" in project.load_errors[0].message


def test_malformed_action_xml_is_a_load_error(builder):
    builder.action("Broken", "A", meta="<GenAiFunction>")
    assert "well-formed" in builder.load().load_errors[0].message


def test_a_bad_schema_is_a_load_error_but_the_action_still_loads(builder):
    builder.action("Act", "A")
    builder.write("genAiFunctions/Act/input/schema.json", "[]")
    project = builder.load()
    assert "Act" in project.actions and project.actions["Act"].input_schema is None
    assert len(project.load_errors) == 1


def test_a_bad_apex_file_is_a_load_error_and_the_rest_still_loads(builder):
    builder.apex("Good", [("String", "a")], [])
    builder.apex("Bad", source="// not a class")
    project = builder.load()
    assert set(project.apex_targets) == {"Good"} and len(project.load_errors) == 1


def test_a_bad_flow_file_is_a_load_error(builder):
    builder.flow("Bad", source="<Flow>")
    assert "well-formed" in builder.load().load_errors[0].message


def test_a_bad_topic_file_is_a_load_error(builder):
    builder.write("genAiPlugins/Bad.genAiPlugin-meta.xml", "<GenAiPlugin>")
    assert len(builder.load().load_errors) == 1


def test_a_bad_planner_bundle_is_a_load_error(builder):
    builder.write("genAiPlannerBundles/B/B.genAiPlannerBundle-meta.xml", "<x")
    assert len(builder.load().load_errors) == 1


def test_an_action_without_schemas_loads_with_none_on_both_sides(builder):
    builder.action("Act", "A")
    action = builder.load().actions["Act"]
    assert action.input_schema is None and action.output_schema is None


def test_the_invocation_target_type_is_lower_cased(builder):
    builder.action("Act", "A", target_type="Apex")
    assert builder.load().actions["Act"].invocation_target_type == "apex"


def test_target_for_returns_none_for_an_unsupported_target_type(builder):
    builder.action("Act", "A", target_type="prompt")
    project = builder.load()
    assert project.target_for(project.actions["Act"]) is None


def test_confirmation_required_is_read(builder):
    meta = (
        f'<?xml version="1.0"?><GenAiFunction {NS}><invocationTarget>A</invocationTarget>'
        "<invocationTargetType>apex</invocationTargetType>"
        "<isConfirmationRequired>true</isConfirmationRequired></GenAiFunction>"
    )
    builder.action("Act", "A", meta=meta)
    assert builder.load().actions["Act"].confirmation_required is True


def test_multiple_package_directories_are_all_scanned(tmp_path):
    (tmp_path / "sfdx-project.json").write_text(
        json.dumps({"packageDirectories": [{"path": "one"}, {"path": "two"}]})
    )
    for pkg, name in (("one", "A"), ("two", "B")):
        d = tmp_path / pkg / "main" / "default" / "genAiFunctions" / name
        d.mkdir(parents=True)
        (d / f"{name}.genAiFunction-meta.xml").write_text(
            f'<?xml version="1.0"?><GenAiFunction {NS}><invocationTarget>X</invocationTarget>'
            "<invocationTargetType>apex</invocationTargetType></GenAiFunction>"
        )
        (d / "output").mkdir()
        (d / "output" / "schema.json").write_text(
            json.dumps(output_schema({"o": prop("lightning__textType", planner=True)}))
        )
    assert set(load_project(tmp_path).actions) == {"A", "B"}
