"""Properties of the type compatibility rules, the heart of ADR-001."""

import pytest

from afcl.schema import SchemaProperty
from afcl.targets import (
    KIND_BOOLEAN,
    KIND_DATE,
    KIND_DATETIME,
    KIND_ID,
    KIND_INTEGER,
    KIND_LIST,
    KIND_NUMBER,
    KIND_TEXT,
    KIND_UNDECIDABLE,
    TargetSignature,
    Variable,
    compatible,
)


def var(kind: str) -> Variable:
    return Variable(name="x", declared_type=kind, kind=kind)


def sp(ltype: str) -> SchemaProperty:
    return SchemaProperty(name="x", lightning_type=ltype)


@pytest.mark.parametrize(
    "kind,ltype",
    [
        (KIND_TEXT, "lightning__textType"),
        (KIND_TEXT, "lightning__multilineTextType"),
        (KIND_TEXT, "lightning__richTextType"),
        (KIND_TEXT, "lightning__urlType"),
        (KIND_ID, "lightning__recordIdType"),
        (KIND_INTEGER, "lightning__integerType"),
        (KIND_NUMBER, "lightning__numberType"),
        (KIND_BOOLEAN, "lightning__booleanType"),
        (KIND_DATE, "lightning__dateType"),
        (KIND_DATETIME, "lightning__dateTimeType"),
        (KIND_LIST, "lightning__listType"),
    ],
)
def test_each_kind_is_compatible_with_its_exact_schema_type(kind, ltype):
    ok, detail = compatible(var(kind), sp(ltype))
    assert ok and detail == "exact"


def test_every_text_family_member_is_accepted_for_a_string_variable():
    for ltype in ("lightning__textType", "lightning__multilineTextType", "lightning__richTextType"):
        assert compatible(var(KIND_TEXT), sp(ltype))[0]


def test_an_id_declared_as_text_is_a_weakened_mismatch():
    ok, detail = compatible(var(KIND_ID), sp("lightning__textType"))
    assert not ok and detail.startswith("weakened")


def test_an_integer_declared_as_number_is_a_widened_mismatch():
    ok, detail = compatible(var(KIND_INTEGER), sp("lightning__numberType"))
    assert not ok and detail.startswith("widened")


def test_a_number_declared_as_integer_is_a_narrowed_mismatch():
    ok, detail = compatible(var(KIND_NUMBER), sp("lightning__integerType"))
    assert not ok and detail.startswith("narrowed")


def test_a_boolean_declared_as_text_is_a_plain_different_mismatch():
    ok, detail = compatible(var(KIND_BOOLEAN), sp("lightning__textType"))
    assert not ok and detail.startswith("different")


def test_a_date_is_not_compatible_with_a_datetime():
    assert not compatible(var(KIND_DATE), sp("lightning__dateTimeType"))[0]


def test_a_list_is_not_compatible_with_a_scalar():
    assert not compatible(var(KIND_LIST), sp("lightning__textType"))[0]


def test_an_undecidable_variable_is_never_reported_as_a_mismatch():
    ok, detail = compatible(var(KIND_UNDECIDABLE), sp("lightning__textType"))
    assert ok and detail == "undecidable"


def test_a_variable_knows_whether_it_is_decidable():
    assert var(KIND_TEXT).decidable
    assert not var(KIND_UNDECIDABLE).decidable


def test_a_signature_indexes_inputs_and_outputs_by_name():
    sig = TargetSignature(
        name="T",
        target_type="apex",
        source_path="x",
        inputs=[var(KIND_TEXT)],
        outputs=[Variable(name="y", declared_type="Boolean", kind=KIND_BOOLEAN)],
    )
    assert set(sig.inputs_by_name()) == {"x"}
    assert set(sig.outputs_by_name()) == {"y"}


def test_a_signature_is_active_and_invocable_by_default():
    sig = TargetSignature(name="T", target_type="flow", source_path="x")
    assert sig.active and sig.invocable
