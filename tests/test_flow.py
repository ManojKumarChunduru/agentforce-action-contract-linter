"""Properties of the Flow extractor."""

import pytest

from afcl.flow import FlowError, classify_variable, parse_flow, signature
from afcl.targets import (
    KIND_BOOLEAN,
    KIND_DATE,
    KIND_DATETIME,
    KIND_INTEGER,
    KIND_LIST,
    KIND_NUMBER,
    KIND_TEXT,
    KIND_UNDECIDABLE,
)
from tests.conftest import NS, flow_source


def parse(tmp_path, source, name="F"):
    p = tmp_path / f"{name}.flow-meta.xml"
    p.write_text(source)
    return signature(parse_flow(p))


@pytest.mark.parametrize(
    "data_type,scale,kind",
    [
        ("String", "", KIND_TEXT),
        ("Picklist", "", KIND_TEXT),
        ("Number", "0", KIND_INTEGER),
        ("Number", "2", KIND_NUMBER),
        ("Number", "", KIND_NUMBER),
        ("Currency", "2", KIND_NUMBER),
        ("Boolean", "", KIND_BOOLEAN),
        ("Date", "", KIND_DATE),
        ("DateTime", "", KIND_DATETIME),
    ],
)
def test_flow_data_types_map_to_their_kind(data_type, scale, kind):
    assert classify_variable(data_type, False, scale) == (kind, "")


def test_a_collection_of_any_type_is_a_list():
    assert classify_variable("SObject", True, "")[0] == KIND_LIST


def test_an_sobject_variable_is_undecidable_with_a_reason():
    kind, reason = classify_variable("SObject", False, "")
    assert kind == KIND_UNDECIDABLE and "SObject" in reason


def test_an_apex_defined_variable_is_undecidable():
    assert classify_variable("Apex", False, "")[0] == KIND_UNDECIDABLE


def test_an_unknown_data_type_is_undecidable_naming_the_type():
    kind, reason = classify_variable("Mystery", False, "")
    assert kind == KIND_UNDECIDABLE and "Mystery" in reason


def test_input_variables_become_inputs_and_output_variables_become_outputs(tmp_path):
    sig = parse(tmp_path, flow_source("F", [("String", "a")], [("Boolean", "ok")]))
    assert [v.name for v in sig.inputs] == ["a"]
    assert [v.name for v in sig.outputs] == ["ok"]


def test_a_variable_that_is_both_input_and_output_appears_on_both_sides(tmp_path):
    src = (
        f'<?xml version="1.0"?><Flow {NS}><status>Active</status><variables><name>v</name>'
        "<dataType>String</dataType><isInput>true</isInput><isOutput>true</isOutput>"
        "</variables></Flow>"
    )
    sig = parse(tmp_path, src)
    assert [v.name for v in sig.inputs] == ["v"] and [v.name for v in sig.outputs] == ["v"]


def test_a_variable_that_is_neither_input_nor_output_is_ignored(tmp_path):
    src = (
        f'<?xml version="1.0"?><Flow {NS}><status>Active</status><variables><name>local</name>'
        "<dataType>String</dataType></variables></Flow>"
    )
    sig = parse(tmp_path, src)
    assert sig.inputs == [] and sig.outputs == []


def test_flow_inputs_are_never_required_because_flow_has_no_such_flag(tmp_path):
    sig = parse(tmp_path, flow_source("F", [("String", "a")], []))
    assert sig.inputs[0].required is False


def test_a_draft_flow_is_inactive(tmp_path):
    assert parse(tmp_path, flow_source("F", [], [], status="Draft")).active is False


def test_an_active_flow_is_active(tmp_path):
    assert parse(tmp_path, flow_source("F", [], [], status="Active")).active is True


def test_a_flow_with_no_status_element_is_treated_as_active(tmp_path):
    src = f'<?xml version="1.0"?><Flow {NS}></Flow>'
    assert parse(tmp_path, src).active is True


def test_the_object_type_is_kept_in_the_declared_type(tmp_path):
    extra = "        <objectType>Case</objectType>\n"
    sig = parse(tmp_path, flow_source("F", [("SObject", "rec", extra)], []))
    assert sig.inputs[0].declared_type == "SObject<Case>"


def test_a_collection_marks_the_declared_type_with_brackets(tmp_path):
    src = (
        f'<?xml version="1.0"?><Flow {NS}><variables><name>v</name><dataType>String</dataType>'
        "<isCollection>true</isCollection><isInput>true</isInput></variables></Flow>"
    )
    sig = parse(tmp_path, src)
    assert sig.inputs[0].declared_type == "String[]" and sig.inputs[0].kind == KIND_LIST


def test_a_screen_flow_is_noted_as_not_autolaunched(tmp_path):
    src = f'<?xml version="1.0"?><Flow {NS}><processType>Flow</processType></Flow>'
    assert any("AutoLaunchedFlow" in n for n in parse(tmp_path, src).notes)


def test_malformed_xml_is_a_flow_error(tmp_path):
    p = tmp_path / "F.flow-meta.xml"
    p.write_text("<Flow><variables></Flow>")
    with pytest.raises(FlowError, match="well-formed"):
        parse_flow(p)


def test_a_non_flow_root_is_a_flow_error(tmp_path):
    p = tmp_path / "F.flow-meta.xml"
    p.write_text(f'<?xml version="1.0"?><ApexClass {NS}></ApexClass>')
    with pytest.raises(FlowError, match="not Flow"):
        parse_flow(p)


def test_the_flow_name_comes_from_the_file_name_not_the_label(tmp_path):
    sig = parse(tmp_path, flow_source("Pretty Label", [], []), name="Api_Name")
    assert sig.name == "Api_Name" and sig.target_type == "flow"
