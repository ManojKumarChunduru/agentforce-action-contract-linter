"""The shape every invocable target reduces to, whatever language it was written in.

Apex and Flow describe their inputs differently (an `@InvocableVariable` on a field versus a
`<variables>` block with `isInput`), but the reconciler only needs one question answered per
variable: what kind of value does the target expect here, and is it required. This module is the
meeting point. `apex.py` and `flow.py` each produce a `TargetSignature`, and `contracts.py` never
has to know which one it is looking at.

The kind vocabulary is deliberately smaller than either language. A kind of `undecidable` is a
first class value, not an exception: it is how the extractors say "I will not guess", and the
report counts those separately from drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from afcl.schema import TEXT_FAMILY, SchemaProperty

KIND_TEXT = "text"
KIND_ID = "id"
KIND_INTEGER = "integer"
KIND_NUMBER = "number"
KIND_BOOLEAN = "boolean"
KIND_DATE = "date"
KIND_DATETIME = "datetime"
KIND_LIST = "list"
KIND_UNDECIDABLE = "undecidable"

DECIDABLE_KINDS: frozenset[str] = frozenset(
    {
        KIND_TEXT,
        KIND_ID,
        KIND_INTEGER,
        KIND_NUMBER,
        KIND_BOOLEAN,
        KIND_DATE,
        KIND_DATETIME,
        KIND_LIST,
    }
)

_EXACT: dict[str, frozenset[str]] = {
    KIND_TEXT: TEXT_FAMILY,
    KIND_ID: frozenset({"lightning__recordIdType"}),
    KIND_INTEGER: frozenset({"lightning__integerType"}),
    KIND_NUMBER: frozenset({"lightning__numberType"}),
    KIND_BOOLEAN: frozenset({"lightning__booleanType"}),
    KIND_DATE: frozenset({"lightning__dateType"}),
    KIND_DATETIME: frozenset({"lightning__dateTimeType"}),
    KIND_LIST: frozenset({"lightning__listType"}),
}


@dataclass(frozen=True)
class Variable:
    """One input or output of a target.

    `declared_type` is the type as written in the source (`Id`, `List<String>`, `SObject`), kept
    for the report. `kind` is the reconciler's view of it. `reason` is set only when the kind is
    undecidable and says why the extractor refused.
    """

    name: str
    declared_type: str
    kind: str
    required: bool = False
    label: str = ""
    description: str = ""
    reason: str = ""

    @property
    def decidable(self) -> bool:
        return self.kind in DECIDABLE_KINDS


@dataclass
class TargetSignature:
    """What one invocable target accepts and returns."""

    name: str
    target_type: str
    source_path: str
    inputs: list[Variable] = field(default_factory=list)
    outputs: list[Variable] = field(default_factory=list)
    active: bool = True
    invocable: bool = True
    notes: list[str] = field(default_factory=list)

    def inputs_by_name(self) -> dict[str, Variable]:
        return {v.name: v for v in self.inputs}

    def outputs_by_name(self) -> dict[str, Variable]:
        return {v.name: v for v in self.outputs}


def compatible(variable: Variable, prop: SchemaProperty) -> tuple[bool, str]:
    """Return (ok, detail). Detail names the direction of a mismatch for the report.

    A target `Id` declared as text in the schema is the most common real drift: it still runs,
    and the planner stops validating that the value is a record ID. That is reported as a mismatch
    with the detail `weakened`, so the reader can see it is a loss of validation rather than a
    runtime break. The direction labels are descriptive only; severity is decided in contracts.
    """
    if not variable.decidable:
        return True, "undecidable"
    allowed = _EXACT[variable.kind]
    if prop.lightning_type in allowed:
        return True, "exact"
    if variable.kind == KIND_ID and prop.lightning_type in TEXT_FAMILY:
        return False, "weakened: target expects a record ID, schema declares free text"
    if variable.kind == KIND_INTEGER and prop.lightning_type == "lightning__numberType":
        return False, "widened: target expects an integer, schema allows decimals"
    if variable.kind == KIND_NUMBER and prop.lightning_type == "lightning__integerType":
        return False, "narrowed: target accepts decimals, schema only offers integers"
    return False, f"different: target kind {variable.kind}, schema type {prop.lightning_type}"
