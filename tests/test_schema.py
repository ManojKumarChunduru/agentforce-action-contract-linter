"""Properties of schema.json loading: the planner's half of the contract."""

import json
from pathlib import Path

import pytest

from afcl.schema import KNOWN_TYPES, TEXT_CAP, SchemaError, SchemaProperty, load_schema
from tests.conftest import input_schema, output_schema, prop


def write(tmp_path: Path, data) -> Path:
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return p


def test_a_valid_input_schema_yields_one_property_per_entry(tmp_path):
    p = write(
        tmp_path,
        input_schema({"a": prop("lightning__textType"), "b": prop("lightning__integerType")}),
    )
    schema = load_schema(p, "input")
    assert [sp.name for sp in schema.properties] == ["a", "b"]


def test_required_names_are_marked_required_on_the_property(tmp_path):
    p = write(tmp_path, input_schema({"a": prop("lightning__textType")}, required=["a"]))
    assert load_schema(p, "input").by_name()["a"].required is True


def test_names_outside_the_required_list_are_optional(tmp_path):
    p = write(tmp_path, input_schema({"a": prop("lightning__textType")}))
    assert load_schema(p, "input").by_name()["a"].required is False


def test_the_planner_flag_is_read_from_a_boolean(tmp_path):
    p = write(tmp_path, output_schema({"a": prop("lightning__textType", planner=True)}))
    assert load_schema(p, "output").planner_usable[0].name == "a"


def test_the_planner_flag_is_read_from_the_string_true(tmp_path):
    p = write(
        tmp_path,
        output_schema(
            {"a": prop("lightning__textType", **{"copilotAction:isUsedByPlanner": "true"})}
        ),
    )
    assert load_schema(p, "output").planner_usable


def test_a_planner_flag_with_an_unexpected_value_counts_as_false(tmp_path):
    p = write(
        tmp_path,
        output_schema({"a": prop("lightning__textType", **{"copilotAction:isUsedByPlanner": 1})}),
    )
    assert not load_schema(p, "output").planner_usable


def test_an_output_schema_with_no_planner_usable_property_reports_an_empty_list(tmp_path):
    p = write(tmp_path, output_schema({"a": prop("lightning__textType")}))
    assert load_schema(p, "output").planner_usable == []


def test_invalid_json_is_a_schema_error_naming_the_line(tmp_path):
    p = write(tmp_path, "{\n  'single quotes': 1\n}")
    with pytest.raises(SchemaError, match="line 2"):
        load_schema(p, "input")


def test_a_top_level_that_is_not_an_object_type_is_refused(tmp_path):
    p = write(tmp_path, {"lightning:type": "lightning__textType", "properties": {}})
    with pytest.raises(SchemaError, match="lightning__objectType"):
        load_schema(p, "input")


def test_a_top_level_list_is_refused(tmp_path):
    p = write(tmp_path, [1, 2])
    with pytest.raises(SchemaError, match="top level"):
        load_schema(p, "input")


def test_properties_that_is_not_an_object_is_refused(tmp_path):
    p = write(tmp_path, {"lightning:type": "lightning__objectType", "properties": []})
    with pytest.raises(SchemaError, match="properties"):
        load_schema(p, "input")


def test_required_that_is_not_a_list_of_names_is_refused(tmp_path):
    p = write(
        tmp_path, {"lightning:type": "lightning__objectType", "properties": {}, "required": "a"}
    )
    with pytest.raises(SchemaError, match="required"):
        load_schema(p, "input")


def test_a_required_name_with_no_property_is_refused(tmp_path):
    p = write(tmp_path, input_schema({"a": prop("lightning__textType")}, required=["b"]))
    with pytest.raises(SchemaError, match="'b'"):
        load_schema(p, "input")


def test_a_property_without_a_lightning_type_is_refused(tmp_path):
    p = write(tmp_path, input_schema({"a": {"title": "A"}}))
    with pytest.raises(SchemaError, match="lightning:type"):
        load_schema(p, "input")


def test_a_property_that_is_not_an_object_is_refused(tmp_path):
    p = write(tmp_path, input_schema({"a": "text"}))
    with pytest.raises(SchemaError, match="'a'"):
        load_schema(p, "input")


def test_a_non_integer_max_length_is_refused(tmp_path):
    p = write(tmp_path, input_schema({"a": prop("lightning__textType", maxLength="250")}))
    with pytest.raises(SchemaError, match="maxLength"):
        load_schema(p, "input")


def test_kind_must_be_input_or_output():
    with pytest.raises(ValueError, match="kind"):
        load_schema(Path("x"), "sideways")


def test_a_text_property_above_the_cap_is_flagged():
    sp = SchemaProperty(name="a", lightning_type="lightning__textType", max_length=TEXT_CAP + 1)
    assert sp.exceeds_text_cap


def test_a_text_property_at_the_cap_is_not_flagged():
    sp = SchemaProperty(name="a", lightning_type="lightning__textType", max_length=TEXT_CAP)
    assert not sp.exceeds_text_cap


def test_a_non_text_property_with_a_large_max_length_is_not_flagged():
    sp = SchemaProperty(name="a", lightning_type="lightning__integerType", max_length=5000)
    assert not sp.exceeds_text_cap


def test_unknown_lightning_types_are_listed_not_rejected(tmp_path):
    p = write(tmp_path, input_schema({"a": prop("lightning__mysteryType")}))
    schema = load_schema(p, "input")
    assert [sp.name for sp in schema.unknown_types] == ["a"]


def test_the_known_type_vocabulary_has_twelve_entries():
    assert len(KNOWN_TYPES) == 12


def test_pii_and_user_input_flags_are_read(tmp_path):
    p = write(
        tmp_path,
        input_schema(
            {
                "a": prop(
                    "lightning__textType",
                    **{"lightning:isPII": True, "copilotAction:isUserInput": True},
                )
            }
        ),
    )
    sp = load_schema(p, "input").by_name()["a"]
    assert sp.is_pii and sp.is_user_input
