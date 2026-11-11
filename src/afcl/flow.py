"""Flow metadata as a target: input and output variables, and whether the Flow is active.

A Flow's contract with the planner is its `<variables>` blocks flagged `isInput` or `isOutput`.
Flow has no notion of a required input, so the reconciler can never say "the Flow needed this and
the schema did not supply it" with the confidence it has for Apex; it can only say the schema
covers or does not cover each input. That asymmetry is recorded, not papered over.

`SObject` and `Apex` typed variables are refused as undecidable for the same reason the Apex
extractor refuses them: there is no `lightning:type` that carries a record, so there is nothing
in the schema to compare them against.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from afcl.targets import (
    KIND_BOOLEAN,
    KIND_DATE,
    KIND_DATETIME,
    KIND_INTEGER,
    KIND_LIST,
    KIND_NUMBER,
    KIND_TEXT,
    KIND_UNDECIDABLE,
    TargetSignature,
    Variable,
)

NS = {"m": "http://soap.sforce.com/2006/04/metadata"}


class FlowError(ValueError):
    """The file could not be read as a Flow."""


@dataclass
class FlowDefinition:
    name: str
    path: Path
    status: str
    process_type: str
    variables: list[Variable] = field(default_factory=list)
    output_variables: list[Variable] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _text(node: ET.Element | None, tag: str, default: str = "") -> str:
    if node is None:
        return default
    child = node.find(f"m:{tag}", NS)
    return (child.text or "").strip() if child is not None and child.text else default


def classify_variable(data_type: str, is_collection: bool, scale: str) -> tuple[str, str]:
    """Map a Flow variable to a reconciler kind. Returns (kind, reason)."""
    if is_collection:
        return KIND_LIST, ""
    lowered = data_type.lower()
    if lowered in ("string", "picklist"):
        return KIND_TEXT, ""
    if lowered in ("number", "currency"):
        return (KIND_INTEGER, "") if scale == "0" else (KIND_NUMBER, "")
    if lowered == "boolean":
        return KIND_BOOLEAN, ""
    if lowered == "date":
        return KIND_DATE, ""
    if lowered == "datetime":
        return KIND_DATETIME, ""
    if lowered == "sobject":
        return KIND_UNDECIDABLE, "SObject variable; no lightning:type carries records"
    if lowered == "apex":
        return KIND_UNDECIDABLE, "Apex-defined variable; its fields are not visible in Flow XML"
    return KIND_UNDECIDABLE, f"Flow dataType {data_type!r} is outside the subset"


def parse_flow(path: Path) -> FlowDefinition:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise FlowError(f"{path}: not well-formed XML ({exc})") from exc
    if root.tag != "{http://soap.sforce.com/2006/04/metadata}Flow":
        raise FlowError(f"{path}: root element is not Flow")
    name = path.name.split(".")[0]
    flow = FlowDefinition(
        name=name,
        path=path,
        status=_text(root, "status", "Active"),
        process_type=_text(root, "processType"),
    )
    for var in root.findall("m:variables", NS):
        var_name = _text(var, "name")
        data_type = _text(var, "dataType")
        is_collection = _text(var, "isCollection", "false").lower() == "true"
        is_input = _text(var, "isInput", "false").lower() == "true"
        is_output = _text(var, "isOutput", "false").lower() == "true"
        scale = _text(var, "scale", "")
        object_type = _text(var, "objectType")
        kind, reason = classify_variable(data_type, is_collection, scale)
        declared = data_type
        if object_type:
            declared += f"<{object_type}>"
        if is_collection:
            declared += "[]"
        variable = Variable(
            name=var_name,
            declared_type=declared,
            kind=kind,
            required=False,
            description=_text(var, "description"),
            reason=reason,
        )
        if is_input:
            flow.variables.append(variable)
        if is_output:
            flow.output_variables.append(variable)
    if flow.process_type and flow.process_type != "AutoLaunchedFlow":
        flow.notes.append(f"processType is {flow.process_type}; actions expect AutoLaunchedFlow")
    return flow


def signature(flow: FlowDefinition) -> TargetSignature:
    return TargetSignature(
        name=flow.name,
        target_type="flow",
        source_path=str(flow.path),
        inputs=list(flow.variables),
        outputs=list(flow.output_variables),
        active=flow.status.lower() == "active",
        notes=list(flow.notes),
    )
