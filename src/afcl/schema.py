"""The action schema files, and the type vocabulary the planner speaks.

An Agentforce action declares its contract in two JSON files, `input/schema.json` and
`output/schema.json`, next to the `.genAiFunction-meta.xml`. The planner reads these, not the Apex
or the Flow. This module turns them into a model the reconciler can compare against a target
signature, and it owns the documented facts about the vocabulary: which `lightning:type` values
exist, that text is capped at 250 characters, and that an output schema needs at least one property
the planner is allowed to use.

Those documented facts are kept here, in one place, because the severity policy in `contracts.py`
leans on them and a reviewer should be able to find the source of each in one file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

OBJECT_TYPE = "lightning__objectType"
TEXT_CAP = 250
"""Documented cap on text-typed properties, from the GenAiFunction metadata reference."""

KNOWN_TYPES: frozenset[str] = frozenset(
    {
        "lightning__textType",
        "lightning__multilineTextType",
        "lightning__richTextType",
        "lightning__integerType",
        "lightning__numberType",
        "lightning__booleanType",
        "lightning__dateType",
        "lightning__dateTimeType",
        "lightning__recordIdType",
        "lightning__urlType",
        "lightning__listType",
        OBJECT_TYPE,
    }
)

TEXT_FAMILY: frozenset[str] = frozenset(
    {
        "lightning__textType",
        "lightning__multilineTextType",
        "lightning__richTextType",
        "lightning__urlType",
    }
)

USED_BY_PLANNER = "copilotAction:isUsedByPlanner"
IS_USER_INPUT = "copilotAction:isUserInput"
IS_DISPLAYABLE = "copilotAction:isDisplayable"


class SchemaError(ValueError):
    """The schema file could not be read as an action schema."""


@dataclass(frozen=True)
class SchemaProperty:
    name: str
    lightning_type: str
    title: str = ""
    description: str = ""
    required: bool = False
    max_length: int | None = None
    used_by_planner: bool = False
    is_user_input: bool = False
    is_displayable: bool = False
    is_pii: bool = False

    @property
    def is_text(self) -> bool:
        return self.lightning_type in TEXT_FAMILY

    @property
    def exceeds_text_cap(self) -> bool:
        return self.is_text and self.max_length is not None and self.max_length > TEXT_CAP


@dataclass
class ActionSchema:
    kind: str
    path: Path
    properties: list[SchemaProperty] = field(default_factory=list)
    required: tuple[str, ...] = ()

    def by_name(self) -> dict[str, SchemaProperty]:
        return {p.name: p for p in self.properties}

    @property
    def planner_usable(self) -> list[SchemaProperty]:
        return [p for p in self.properties if p.used_by_planner]

    @property
    def unknown_types(self) -> list[SchemaProperty]:
        return [p for p in self.properties if p.lightning_type not in KNOWN_TYPES]


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def load_schema(path: Path, kind: str) -> ActionSchema:
    """Read one schema.json. Raises SchemaError for anything that is not an action schema.

    A missing file is not an error here: an action with no input schema is a legitimate shape (an
    action that takes nothing). The caller decides what a missing file means.
    """
    if kind not in ("input", "output"):
        raise ValueError(f"kind must be input or output, got {kind!r}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{path}: not valid JSON ({exc.msg} at line {exc.lineno})") from exc
    if not isinstance(raw, dict):
        raise SchemaError(f"{path}: top level must be an object")
    top_type = raw.get("lightning:type")
    if top_type != OBJECT_TYPE:
        raise SchemaError(
            f"{path}: top level lightning:type must be {OBJECT_TYPE}, got {top_type!r}"
        )
    props_raw = raw.get("properties", {})
    if not isinstance(props_raw, dict):
        raise SchemaError(f"{path}: properties must be an object")
    required_raw = raw.get("required", [])
    if not isinstance(required_raw, list) or not all(isinstance(r, str) for r in required_raw):
        raise SchemaError(f"{path}: required must be a list of property names")
    required = tuple(required_raw)
    for name in required:
        if name not in props_raw:
            raise SchemaError(f"{path}: required names {name!r} which is not a property")

    properties: list[SchemaProperty] = []
    for name, spec in props_raw.items():
        if not isinstance(spec, dict):
            raise SchemaError(f"{path}: property {name!r} must be an object")
        ltype = spec.get("lightning:type")
        if not isinstance(ltype, str) or not ltype:
            raise SchemaError(f"{path}: property {name!r} has no lightning:type")
        max_length = spec.get("maxLength")
        if max_length is not None and not isinstance(max_length, int):
            raise SchemaError(f"{path}: property {name!r} maxLength must be an integer")
        properties.append(
            SchemaProperty(
                name=name,
                lightning_type=ltype,
                title=str(spec.get("title", "")),
                description=str(spec.get("description", "")),
                required=name in required,
                max_length=max_length,
                used_by_planner=_as_bool(spec.get(USED_BY_PLANNER)),
                is_user_input=_as_bool(spec.get(IS_USER_INPUT)),
                is_displayable=_as_bool(spec.get(IS_DISPLAYABLE)),
                is_pii=_as_bool(spec.get("lightning:isPII")),
            )
        )
    return ActionSchema(kind=kind, path=path, properties=properties, required=required)
