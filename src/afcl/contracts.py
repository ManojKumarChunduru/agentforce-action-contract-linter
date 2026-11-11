"""The reconciliation itself: the edge the metadata does not have, drawn and checked.

For every action, this module pairs each schema property with the target variable of the same
name and asks three questions the deploy never asks: does the other side exist, do the types
agree, and does the required-ness agree. Then it asks two more at the graph level: does any topic
reach this action, and does every topic's action exist. Each answer that comes back wrong is a
`Finding` with a drift class.

Three design choices live here and are worth reading before the code:

1. Severity is about whether the action can run as described (fatal), runs but is misdescribed
   (warn), or is merely dead (info). It is not about how confident the linter is. Confidence is a
   separate column, `evidence`, which says whether the runtime consequence is documented by
   Salesforce or inferred from the contract. Experiment 4 publishes that table; ADR-003 explains
   why the two are kept apart.
2. `undecidable` is not a finding. It is the linter saying it could not check a property, and it
   is counted and reported on its own so a clean report cannot hide an unchecked action.
3. `name_only=True` runs the reconciliation the way a careful human reviewer does it, by names
   alone. Experiment 2 uses it to measure what that review misses; it is not a mode the CLI offers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from afcl.project import ActionDefinition, Project
from afcl.schema import TEXT_CAP
from afcl.targets import TargetSignature, compatible
from afcl.topics import reachable_actions

FATAL = "fatal"
WARN = "warn"
INFO = "info"

DOCUMENTED = "documented"
INFERRED = "inferred"


@dataclass(frozen=True)
class DriftClass:
    name: str
    severity: str
    evidence: str
    summary: str
    consequence: str
    name_visible: bool
    """Whether a name-only review (matching property names, nothing else) can see it."""


DRIFT_CLASSES: dict[str, DriftClass] = {
    dc.name: dc
    for dc in (
        DriftClass(
            "missing_target",
            FATAL,
            INFERRED,
            "invocationTarget names an Apex class or Flow that is not in the project, or an "
            "Apex class with no @InvocableMethod",
            "there is nothing for the planner to invoke",
            True,
        ),
        DriftClass(
            "target_inactive",
            FATAL,
            INFERRED,
            "the Flow behind the action is not Active",
            "an inactive Flow cannot be launched by an action",
            False,
        ),
        DriftClass(
            "no_planner_output",
            FATAL,
            DOCUMENTED,
            "no output property is marked copilotAction:isUsedByPlanner",
            "the GenAiFunction reference states the planner returns random responses",
            False,
        ),
        DriftClass(
            "dangling_topic_function",
            FATAL,
            INFERRED,
            "a topic lists a functionName that is not an action in the project",
            "the topic promises an action the planner cannot find",
            True,
        ),
        DriftClass(
            "orphan_input",
            WARN,
            INFERRED,
            "the input schema declares a property the target has no variable for",
            "the planner collects a value that is silently dropped",
            True,
        ),
        DriftClass(
            "uncovered_input",
            WARN,
            INFERRED,
            "the target accepts an input the schema never declares",
            "the planner can never supply it, so the target always sees null",
            True,
        ),
        DriftClass(
            "missing_required_input",
            WARN,
            INFERRED,
            "an @InvocableVariable(required=true) is absent from the schema or not in its "
            "required list",
            "the planner may call the action without a value Apex insists on",
            True,
        ),
        DriftClass(
            "type_mismatch",
            WARN,
            INFERRED,
            "a schema property and the target variable of the same name disagree on type",
            "validation is weakened, widened or lost at the boundary",
            False,
        ),
        DriftClass(
            "orphan_output",
            WARN,
            INFERRED,
            "the output schema declares a property the target never produces",
            "the planner reasons over a field that is always empty",
            True,
        ),
        DriftClass(
            "text_cap_exceeded",
            WARN,
            DOCUMENTED,
            f"a text property declares maxLength above the documented cap of {TEXT_CAP}",
            f"the reference caps text types at {TEXT_CAP} characters",
            False,
        ),
        DriftClass(
            "unreachable_action",
            INFO,
            INFERRED,
            "no topic lists the action",
            "the planner never sees it; the action is dead metadata",
            True,
        ),
    )
}


@dataclass(frozen=True)
class Finding:
    drift_class: str
    action: str
    message: str
    target: str = ""
    target_type: str = ""
    property_name: str = ""
    detail: str = ""
    path: str = ""

    @property
    def severity(self) -> str:
        return DRIFT_CLASSES[self.drift_class].severity


@dataclass(frozen=True)
class Undecidable:
    action: str
    target: str
    target_type: str
    variable: str
    declared_type: str
    reason: str
    side: str


@dataclass
class LintReport:
    actions_total: int
    topics_total: int
    planners_total: int
    findings: list[Finding] = field(default_factory=list)
    undecidables: list[Undecidable] = field(default_factory=list)
    name_only: bool = False

    def by_class(self) -> Counter[str]:
        return Counter(f.drift_class for f in self.findings)

    def by_severity(self) -> Counter[str]:
        return Counter(f.severity for f in self.findings)

    def by_target_type(self) -> Counter[str]:
        return Counter(f.target_type or "none" for f in self.findings)

    def actions_with_findings(self) -> set[str]:
        return {f.action for f in self.findings if f.drift_class != "dangling_topic_function"}

    def actions_undecidable(self) -> set[str]:
        return {u.action for u in self.undecidables}

    def failing(self, strict: bool = False) -> list[Finding]:
        if strict:
            return [f for f in self.findings if f.severity in (FATAL, WARN)]
        return [f for f in self.findings if f.severity == FATAL]

    def should_fail(self, strict: bool = False) -> bool:
        if self.failing(strict):
            return True
        return strict and bool(self.undecidables)


def _reconcile_inputs(
    action: ActionDefinition,
    target: TargetSignature,
    findings: list[Finding],
    undecidables: list[Undecidable],
    name_only: bool,
) -> None:
    schema = action.input_schema
    schema_props = schema.by_name() if schema else {}
    target_inputs = target.inputs_by_name()
    base = {
        "action": action.name,
        "target": target.name,
        "target_type": target.target_type,
    }
    for name, prop in schema_props.items():
        if name not in target_inputs:
            findings.append(
                Finding(
                    "orphan_input",
                    message=f"input {name!r} has no variable on {target.name}",
                    property_name=name,
                    path=str(schema.path) if schema else "",
                    **base,
                )
            )
            continue
        var = target_inputs[name]
        if not var.decidable:
            undecidables.append(
                Undecidable(
                    action.name,
                    target.name,
                    target.target_type,
                    name,
                    var.declared_type,
                    var.reason,
                    "input",
                )
            )
        elif not name_only:
            ok, detail = compatible(var, prop)
            if not ok:
                findings.append(
                    Finding(
                        "type_mismatch",
                        message=(
                            f"input {name!r}: schema {prop.lightning_type}, "
                            f"target {var.declared_type}"
                        ),
                        property_name=name,
                        detail=detail,
                        path=str(schema.path) if schema else "",
                        **base,
                    )
                )
        if var.required and not prop.required and not name_only:
            findings.append(
                Finding(
                    "missing_required_input",
                    message=(
                        f"input {name!r} is required by {target.name} but optional in the schema"
                    ),
                    property_name=name,
                    detail="optional_in_schema",
                    path=str(schema.path) if schema else "",
                    **base,
                )
            )
        if prop.exceeds_text_cap and not name_only:
            findings.append(
                Finding(
                    "text_cap_exceeded",
                    message=(
                        f"input {name!r} declares maxLength {prop.max_length}, cap is {TEXT_CAP}"
                    ),
                    property_name=name,
                    detail=str(prop.max_length),
                    path=str(schema.path) if schema else "",
                    **base,
                )
            )
    for name, var in target_inputs.items():
        if name in schema_props:
            continue
        if var.required:
            findings.append(
                Finding(
                    "missing_required_input",
                    message=(
                        f"input {name!r} is required by {target.name} and absent from the schema"
                    ),
                    property_name=name,
                    detail="absent",
                    path=target.source_path,
                    **base,
                )
            )
        else:
            findings.append(
                Finding(
                    "uncovered_input",
                    message=f"{target.name} accepts {name!r} but the schema never declares it",
                    property_name=name,
                    path=target.source_path,
                    **base,
                )
            )


def _reconcile_outputs(
    action: ActionDefinition,
    target: TargetSignature,
    findings: list[Finding],
    undecidables: list[Undecidable],
    name_only: bool,
) -> None:
    schema = action.output_schema
    schema_props = schema.by_name() if schema else {}
    target_outputs = target.outputs_by_name()
    base = {
        "action": action.name,
        "target": target.name,
        "target_type": target.target_type,
    }
    for name, prop in schema_props.items():
        if name not in target_outputs:
            findings.append(
                Finding(
                    "orphan_output",
                    message=f"output {name!r} is never produced by {target.name}",
                    property_name=name,
                    path=str(schema.path) if schema else "",
                    **base,
                )
            )
            continue
        var = target_outputs[name]
        if not var.decidable:
            undecidables.append(
                Undecidable(
                    action.name,
                    target.name,
                    target.target_type,
                    name,
                    var.declared_type,
                    var.reason,
                    "output",
                )
            )
        elif not name_only:
            ok, detail = compatible(var, prop)
            if not ok:
                findings.append(
                    Finding(
                        "type_mismatch",
                        message=(
                            f"output {name!r}: schema {prop.lightning_type}, "
                            f"target {var.declared_type}"
                        ),
                        property_name=name,
                        detail=detail,
                        path=str(schema.path) if schema else "",
                        **base,
                    )
                )
        if prop.exceeds_text_cap and not name_only:
            findings.append(
                Finding(
                    "text_cap_exceeded",
                    message=(
                        f"output {name!r} declares maxLength {prop.max_length}, cap is {TEXT_CAP}"
                    ),
                    property_name=name,
                    detail=str(prop.max_length),
                    path=str(schema.path) if schema else "",
                    **base,
                )
            )
    if not name_only and (schema is None or not schema.planner_usable):
        findings.append(
            Finding(
                "no_planner_output",
                message=(
                    f"no output property of {action.name} is marked copilotAction:isUsedByPlanner"
                ),
                path=str(schema.path) if schema else str(action.path),
                **base,
            )
        )


def reconcile(project: Project, name_only: bool = False) -> LintReport:
    """Reconcile every action and topic in the project.

    Pure: reads the project, returns a report, touches nothing on disk.
    """
    report = LintReport(
        actions_total=len(project.actions),
        topics_total=len(project.topics),
        planners_total=len(project.planners),
        name_only=name_only,
    )
    findings = report.findings
    undecidables = report.undecidables

    for name in sorted(project.actions):
        action = project.actions[name]
        if action.invocation_target_type not in ("apex", "flow"):
            undecidables.append(
                Undecidable(
                    action.name,
                    action.invocation_target,
                    action.invocation_target_type or "none",
                    "*",
                    action.invocation_target_type or "none",
                    f"target type {action.invocation_target_type or 'none'!r} is outside the "
                    "subset (only apex and flow are reconciled)",
                    "action",
                )
            )
            continue
        target = project.target_for(action)
        if target is None or not target.invocable:
            detail = "not in project" if target is None else "class has no @InvocableMethod"
            findings.append(
                Finding(
                    "missing_target",
                    action=action.name,
                    message=(
                        f"{action.invocation_target_type} target {action.invocation_target!r}"
                    ),
                    target=action.invocation_target,
                    target_type=action.invocation_target_type,
                    detail=detail,
                    path=str(action.path),
                )
            )
            continue
        if not target.active and not name_only:
            findings.append(
                Finding(
                    "target_inactive",
                    action=action.name,
                    message=f"Flow {target.name} is not Active",
                    target=target.name,
                    target_type=target.target_type,
                    path=target.source_path,
                )
            )
        _reconcile_inputs(action, target, findings, undecidables, name_only)
        _reconcile_outputs(action, target, findings, undecidables, name_only)

    reachable = reachable_actions(project.topics)
    for name in sorted(project.actions):
        if name not in reachable:
            findings.append(
                Finding(
                    "unreachable_action",
                    action=name,
                    message=f"no topic lists {name}",
                    target=project.actions[name].invocation_target,
                    target_type=project.actions[name].invocation_target_type,
                    path=str(project.actions[name].path),
                )
            )
    for topic_name in sorted(project.topics):
        topic = project.topics[topic_name]
        for fn in topic.functions:
            if fn not in project.actions:
                findings.append(
                    Finding(
                        "dangling_topic_function",
                        action=fn,
                        message=f"topic {topic_name} lists {fn!r}, which is not an action",
                        target=topic_name,
                        target_type="topic",
                        path=str(topic.path),
                    )
                )
    return report
