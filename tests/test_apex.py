"""Properties of the Apex extractor: reads the invocable subset, refuses the rest (ADR-002)."""

from pathlib import Path

import pytest

from afcl.apex import ApexError, classify_type, parse_apex, signature
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
)
from tests.conftest import apex_source


def parse(tmp_path: Path, source: str, name: str = "T"):
    p = tmp_path / f"{name}.cls"
    p.write_text(source)
    return signature(parse_apex(p))


@pytest.mark.parametrize(
    "declared,kind",
    [
        ("String", KIND_TEXT),
        ("Id", KIND_ID),
        ("Integer", KIND_INTEGER),
        ("Long", KIND_INTEGER),
        ("Decimal", KIND_NUMBER),
        ("Double", KIND_NUMBER),
        ("Boolean", KIND_BOOLEAN),
        ("Date", KIND_DATE),
        ("Datetime", KIND_DATETIME),
        ("List<String>", KIND_LIST),
        ("Set<Id>", KIND_LIST),
        ("String[]", KIND_LIST),
    ],
)
def test_scalar_and_collection_types_map_to_their_kind(declared, kind):
    assert classify_type(declared) == (kind, "")


def test_type_classification_ignores_case():
    assert classify_type("string")[0] == KIND_TEXT
    assert classify_type("DATETIME")[0] == KIND_DATETIME


@pytest.mark.parametrize("declared", ["SObject", "Contact", "Account", "My_Object__c"])
def test_sobject_types_are_undecidable_with_a_reason(declared):
    kind, reason = classify_type(declared)
    assert kind == KIND_UNDECIDABLE and "SObject" in reason


def test_map_is_undecidable():
    kind, reason = classify_type("Map<String, Object>")
    assert kind == KIND_UNDECIDABLE and "Map" in reason


def test_object_is_undecidable_because_it_accepts_anything():
    kind, reason = classify_type("Object")
    assert kind == KIND_UNDECIDABLE and "anything" in reason


def test_blob_is_undecidable():
    assert classify_type("Blob")[0] == KIND_UNDECIDABLE


def test_a_custom_apex_type_is_undecidable_not_guessed():
    kind, reason = classify_type("MyWrapper")
    assert kind == KIND_UNDECIDABLE and "custom Apex type" in reason


def test_a_generic_outside_list_set_map_is_undecidable():
    assert classify_type("Iterable<String>")[0] == KIND_UNDECIDABLE


def test_inputs_are_read_from_the_request_class(tmp_path):
    sig = parse(
        tmp_path, apex_source("T", [("String", "a", True), ("Id", "b")], [("Boolean", "ok")])
    )
    assert [(v.name, v.kind, v.required) for v in sig.inputs] == [
        ("a", KIND_TEXT, True),
        ("b", KIND_ID, False),
    ]


def test_outputs_are_read_from_the_response_class(tmp_path):
    sig = parse(
        tmp_path, apex_source("T", [("String", "a")], [("Boolean", "ok"), ("Decimal", "n")])
    )
    assert [(v.name, v.kind) for v in sig.outputs] == [("ok", KIND_BOOLEAN), ("n", KIND_NUMBER)]


def test_label_and_description_are_read_from_the_annotation(tmp_path):
    src = """
    public class T {
        public class Request {
            @InvocableVariable(required=true label='Case Number' description='The number')
            public String caseNumber;
        }
        @InvocableMethod(label='x')
        public static void run(List<Request> r) {}
    }"""
    sig = parse(tmp_path, src)
    assert sig.inputs[0].label == "Case Number"
    assert sig.inputs[0].description == "The number"


def test_annotation_arguments_are_case_insensitive(tmp_path):
    src = """
    public class T {
        public class Request {
            @InvocableVariable(Required=TRUE Label='A')
            public String a;
        }
        @InvocableMethod
        public static void run(List<Request> r) {}
    }"""
    assert parse(tmp_path, src).inputs[0].required is True


def test_a_void_method_has_no_outputs(tmp_path):
    src = """
    public class T {
        public class Request { @InvocableVariable public String a; }
        @InvocableMethod
        public static void run(List<Request> r) {}
    }"""
    assert parse(tmp_path, src).outputs == []


def test_a_class_without_an_invocable_method_is_not_invocable(tmp_path):
    src = "public class T { public static String f() { return 'x'; } }"
    sig = parse(tmp_path, src)
    assert not sig.invocable and "no @InvocableMethod" in sig.notes[0]


def test_a_file_with_no_class_is_an_apex_error(tmp_path):
    p = tmp_path / "T.cls"
    p.write_text("// nothing here")
    with pytest.raises(ApexError, match="no class"):
        parse_apex(p)


def test_unbalanced_braces_are_an_apex_error(tmp_path):
    p = tmp_path / "T.cls"
    p.write_text("public class T { public class Request { ")
    with pytest.raises(ApexError, match="unbalanced"):
        parse_apex(p)


def test_braces_inside_comments_do_not_confuse_the_extractor(tmp_path):
    src = """
    public class T {
        // a stray } in a comment
        /* and another { here */
        public class Request { @InvocableVariable public String a; }
        @InvocableMethod
        public static void run(List<Request> r) {}
    }"""
    assert [v.name for v in parse(tmp_path, src).inputs] == ["a"]


def test_braces_inside_string_literals_do_not_confuse_the_extractor(tmp_path):
    src = """
    public class T {
        public static String s = '}{';
        public class Request { @InvocableVariable public String a; }
        @InvocableMethod
        public static void run(List<Request> r) {}
    }"""
    assert [v.name for v in parse(tmp_path, src).inputs] == ["a"]


def test_a_commented_out_invocable_variable_is_not_read(tmp_path):
    src = """
    public class T {
        public class Request {
            @InvocableVariable public String a;
            // @InvocableVariable public String ghost;
        }
        @InvocableMethod
        public static void run(List<Request> r) {}
    }"""
    assert [v.name for v in parse(tmp_path, src).inputs] == ["a"]


def test_a_primitive_list_request_is_undecidable_with_a_reason(tmp_path):
    src = """
    public class T {
        @InvocableMethod
        public static List<String> run(List<Id> ids) { return null; }
    }"""
    sig = parse(tmp_path, src)
    assert sig.inputs[0].kind == KIND_UNDECIDABLE and "primitive" in sig.inputs[0].reason
    assert sig.outputs[0].kind == KIND_UNDECIDABLE


def test_a_non_list_request_parameter_is_undecidable(tmp_path):
    src = """
    public class T {
        @InvocableMethod
        public static void run(String single) {}
    }"""
    sig = parse(tmp_path, src)
    assert sig.inputs[0].kind == KIND_UNDECIDABLE and "List<Request>" in sig.inputs[0].reason


def test_a_method_with_two_parameters_is_noted_and_yields_no_inputs(tmp_path):
    src = """
    public class T {
        @InvocableMethod
        public static void run(List<String> a, List<String> b) {}
    }"""
    sig = parse(tmp_path, src)
    assert sig.inputs == [] and any("2 parameters" in n for n in sig.notes)


def test_two_invocable_methods_are_noted(tmp_path):
    src = """
    public class T {
        public class Request { @InvocableVariable public String a; }
        @InvocableMethod
        public static void run(List<Request> r) {}
        @InvocableMethod
        public static void run2(List<Request> r) {}
    }"""
    assert any("Apex allows one" in n for n in parse(tmp_path, src).notes)


def test_a_non_list_return_type_is_noted(tmp_path):
    src = """
    public class T {
        public class Request { @InvocableVariable public String a; }
        @InvocableMethod
        public static Boolean run(List<Request> r) { return true; }
    }"""
    sig = parse(tmp_path, src)
    assert sig.outputs == [] and any("not List<Response>" in n for n in sig.notes)


def test_a_response_class_declared_after_the_method_is_still_found(tmp_path):
    src = """
    public class T {
        @InvocableMethod
        public static List<Out> run(List<In> r) { return null; }
        public class In { @InvocableVariable public String a; }
        public class Out { @InvocableVariable public Boolean ok; }
    }"""
    sig = parse(tmp_path, src)
    assert [v.name for v in sig.inputs] == ["a"] and [v.name for v in sig.outputs] == ["ok"]


def test_the_outer_class_name_is_the_signature_name(tmp_path):
    sig = parse(tmp_path, apex_source("Named", [("String", "a")], []), name="Named")
    assert sig.name == "Named" and sig.target_type == "apex"


def test_a_global_class_with_a_global_method_is_read(tmp_path):
    src = """
    global with sharing class T {
        global class Request { @InvocableVariable global String a; }
        @InvocableMethod(label='x')
        global static void run(List<Request> r) {}
    }"""
    assert [v.name for v in parse(tmp_path, src).inputs] == ["a"]


def test_an_sobject_field_in_the_request_is_undecidable_but_siblings_are_read(tmp_path):
    src = """
    public class T {
        public class Request {
            @InvocableVariable(required=true) public Contact primary;
            @InvocableVariable public List<Id> dupes;
        }
        @InvocableMethod
        public static void run(List<Request> r) {}
    }"""
    sig = parse(tmp_path, src)
    kinds = {v.name: v.kind for v in sig.inputs}
    assert kinds == {"primary": KIND_UNDECIDABLE, "dupes": KIND_LIST}
