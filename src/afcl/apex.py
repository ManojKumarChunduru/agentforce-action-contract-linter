"""An extractor for the invocable subset of Apex, and nothing more.

The reconciler needs five things from an Apex class: whether it has an `@InvocableMethod`, what
the request type is, which fields of that request carry `@InvocableVariable`, which are required,
and what the response type exposes. A full Apex parser would give all of that and several
thousand productions the linter would never read. This module reads the subset and refuses the
rest, which is ADR-002: a variable whose type is outside the subset comes back as `undecidable`
with a reason, never as a guess.

The refusal is the important design decision. A linter that silently maps `SObject` to "text"
produces a clean report for an action it did not actually check, and a clean report that was not
earned is worse than no report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

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
)

_SCALAR_KINDS: dict[str, str] = {
    "string": KIND_TEXT,
    "id": KIND_ID,
    "integer": KIND_INTEGER,
    "long": KIND_INTEGER,
    "decimal": KIND_NUMBER,
    "double": KIND_NUMBER,
    "boolean": KIND_BOOLEAN,
    "date": KIND_DATE,
    "datetime": KIND_DATETIME,
}

_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_STRING_RE = re.compile(r"'(?:\\.|[^'\\])*'")
_CLASS_RE = re.compile(r"\bclass\s+(\w+)\b[^{]*\{")
_INVOCABLE_METHOD_RE = re.compile(
    r"@InvocableMethod\s*(?:\([^)]*\))?\s*"
    r"(?:(?:public|global|private|protected|static|override|webservice)\s+)*"
    r"(?P<ret>[\w.]+(?:<[^>]*>)?)\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
    re.IGNORECASE,
)
_INVOCABLE_VAR_RE = re.compile(
    r"@InvocableVariable\s*(?:\((?P<args>[^)]*)\))?\s*"
    r"(?:(?:public|global|private|protected|static|final|transient)\s+)*"
    r"(?P<type>[\w.]+(?:<[^>]*>)?(?:\[\])?)\s+(?P<name>\w+)\s*(?:=[^;]*)?;",
    re.IGNORECASE,
)
_ANNOTATION_ARG_RE = re.compile(r"(\w+)\s*=\s*(?:'((?:\\.|[^'\\])*)'|(\w+))")
_GENERIC_RE = re.compile(r"^(?P<outer>[\w.]+)\s*<\s*(?P<inner>.+)\s*>$")


class ApexError(ValueError):
    """The file could not be read as an Apex class at all."""


@dataclass
class ApexClass:
    name: str
    path: Path
    invocable: bool
    method_name: str = ""
    request_type: str = ""
    response_type: str = ""
    inner_classes: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _strip(source: str) -> str:
    """Remove comments, then blank out string literals so braces inside them do not count."""
    without_comments = _COMMENT_RE.sub(" ", source)
    return _STRING_RE.sub(lambda m: "'" + " " * (len(m.group(0)) - 2) + "'", without_comments)


def _preserve_strings(source: str) -> str:
    """Remove comments only. Used to read annotation labels, which live in string literals."""
    return _COMMENT_RE.sub(" ", source)


def _matching_brace(text: str, open_index: int) -> int:
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ApexError("unbalanced braces")


def _classes(text: str) -> list[tuple[str, int, int]]:
    """Every class declaration as (name, body_start, body_end), outermost first."""
    found = []
    for m in _CLASS_RE.finditer(text):
        open_index = m.end() - 1
        close_index = _matching_brace(text, open_index)
        found.append((m.group(1), open_index, close_index))
    return found


def _split_generic(declared: str) -> tuple[str, str | None]:
    m = _GENERIC_RE.match(declared.strip())
    if not m:
        return declared.strip(), None
    return m.group("outer"), m.group("inner").strip()


def classify_type(declared: str) -> tuple[str, str]:
    """Map an Apex type to a reconciler kind. Returns (kind, reason); reason is set when refused."""
    cleaned = declared.strip()
    if cleaned.endswith("[]"):
        return KIND_LIST, ""
    outer, inner = _split_generic(cleaned)
    lowered = outer.lower()
    if inner is None:
        if lowered in _SCALAR_KINDS:
            return _SCALAR_KINDS[lowered], ""
        if lowered == "sobject" or lowered.endswith("__c") or lowered in _SOBJECT_NAMES:
            return KIND_UNDECIDABLE, f"{cleaned} is an SObject; no lightning:type carries records"
        if lowered == "object":
            return KIND_UNDECIDABLE, "Object accepts anything, so no schema type can be checked"
        if lowered == "blob":
            return KIND_UNDECIDABLE, "Blob has no lightning:type equivalent"
        return KIND_UNDECIDABLE, f"{cleaned} is a custom Apex type outside the invocable subset"
    if lowered in ("list", "set"):
        return KIND_LIST, ""
    if lowered == "map":
        return KIND_UNDECIDABLE, f"{cleaned} is a Map; the planner has no key/value type"
    return KIND_UNDECIDABLE, f"{cleaned} is a generic type outside the invocable subset"


_SOBJECT_NAMES: frozenset[str] = frozenset(
    {
        "account",
        "contact",
        "case",
        "lead",
        "opportunity",
        "order",
        "product2",
        "user",
        "task",
        "event",
        "asset",
        "contract",
        "campaign",
    }
)


def _annotation_args(args: str | None) -> dict[str, str]:
    if not args:
        return {}
    out: dict[str, str] = {}
    for m in _ANNOTATION_ARG_RE.finditer(args):
        out[m.group(1).lower()] = m.group(2) if m.group(2) is not None else m.group(3)
    return out


def _variables(body_with_strings: str) -> list[Variable]:
    variables: list[Variable] = []
    for m in _INVOCABLE_VAR_RE.finditer(body_with_strings):
        args = _annotation_args(m.group("args"))
        kind, reason = classify_type(m.group("type"))
        variables.append(
            Variable(
                name=m.group("name"),
                declared_type=m.group("type"),
                kind=kind,
                required=args.get("required", "false").lower() == "true",
                label=args.get("label", ""),
                description=args.get("description", ""),
                reason=reason,
            )
        )
    return variables


def parse_apex(path: Path) -> ApexClass:
    """Read one `.cls` file into an ApexClass. Raises ApexError if it is not a class."""
    source = path.read_text(encoding="utf-8")
    stripped = _strip(source)
    with_strings = _preserve_strings(source)
    classes = _classes(stripped)
    if not classes:
        raise ApexError(f"{path}: no class declaration found")
    outer_name, outer_open, outer_close = classes[0]
    inner: dict[str, str] = {}
    for name, open_index, close_index in classes[1:]:
        if outer_open < open_index < outer_close:
            inner[name] = with_strings[open_index : close_index + 1]
    result = ApexClass(name=outer_name, path=path, invocable=False, inner_classes=inner)

    outer_body = stripped[outer_open : outer_close + 1]
    methods = list(_INVOCABLE_METHOD_RE.finditer(outer_body))
    if not methods:
        result.notes.append("no @InvocableMethod in class")
        return result
    if len(methods) > 1:
        result.notes.append(f"{len(methods)} @InvocableMethod declarations; Apex allows one")
    m = methods[0]
    result.invocable = True
    result.method_name = m.group("name")
    result.response_type = m.group("ret").strip()
    params = [p.strip() for p in m.group("params").split(",") if p.strip()]
    if len(params) != 1:
        result.notes.append(f"invocable method takes {len(params)} parameters; expected one list")
        return result
    type_part = params[0].rsplit(None, 1)[0] if " " in params[0] else params[0]
    result.request_type = type_part.strip()
    return result


def signature(apex_class: ApexClass) -> TargetSignature:
    """Turn a parsed class into the reconciler's view. Unknown shapes become undecidable."""
    sig = TargetSignature(
        name=apex_class.name,
        target_type="apex",
        source_path=str(apex_class.path),
        invocable=apex_class.invocable,
        notes=list(apex_class.notes),
    )
    if not apex_class.invocable or not apex_class.request_type:
        return sig

    req_outer, req_inner = _split_generic(apex_class.request_type)
    if req_outer.lower() != "list" or req_inner is None:
        sig.inputs.append(
            Variable(
                name=apex_class.request_type,
                declared_type=apex_class.request_type,
                kind=KIND_UNDECIDABLE,
                reason="invocable method does not take a List<Request> parameter",
            )
        )
        return sig
    if req_inner in apex_class.inner_classes:
        sig.inputs = _variables(apex_class.inner_classes[req_inner])
    else:
        kind, reason = classify_type(req_inner)
        sig.inputs.append(
            Variable(
                name="request",
                declared_type=req_inner,
                kind=KIND_UNDECIDABLE,
                reason=reason
                or f"request type {req_inner} is a primitive list; the schema names no property",
            )
        )

    resp = apex_class.response_type
    if resp.lower() == "void":
        return sig
    resp_outer, resp_inner = _split_generic(resp)
    if resp_outer.lower() == "list" and resp_inner in apex_class.inner_classes:
        sig.outputs = _variables(apex_class.inner_classes[resp_inner])
    elif resp_outer.lower() == "list" and resp_inner is not None:
        kind, reason = classify_type(resp_inner)
        sig.outputs.append(
            Variable(
                name="response",
                declared_type=resp_inner,
                kind=KIND_UNDECIDABLE,
                reason=reason or f"response type {resp_inner} is a primitive list",
            )
        )
    else:
        sig.notes.append(f"invocable method returns {resp}, which is not List<Response> or void")
    return sig
