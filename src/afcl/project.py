"""Finding the pieces of an SFDX project that an agent is made of.

An agent on disk is scattered across five metadata folders: `genAiPlannerBundles` (the agent),
`genAiPlugins` (topics), `genAiFunctions` (actions, each a folder with two schema files),
`classes` (Apex targets) and `flows` (Flow targets). Nothing links them except names. This module
walks the package directories named in `sfdx-project.json`, loads each piece with the module that
understands it, and hands the reconciler one `Project` with everything indexed by name.

Loading is total: a malformed file is recorded as a load error on the project rather than raised,
so one broken Flow does not hide the drift in thirty healthy actions. The CLI turns load errors
into exit code 2 because a report built on a project the tool could not fully read is not a
report the pipeline should trust.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from afcl import apex, flow
from afcl.schema import ActionSchema, SchemaError, load_schema
from afcl.targets import TargetSignature
from afcl.topics import PlannerBundle, Topic, TopicError, parse_planner_bundle, parse_topic

NS = {"m": "http://soap.sforce.com/2006/04/metadata"}


class ProjectError(ValueError):
    """The directory is not an SFDX project the linter can read."""


@dataclass
class ActionDefinition:
    name: str
    path: Path
    master_label: str = ""
    description: str = ""
    invocation_target: str = ""
    invocation_target_type: str = ""
    confirmation_required: bool = False
    input_schema: ActionSchema | None = None
    output_schema: ActionSchema | None = None


@dataclass
class LoadError:
    path: str
    message: str


@dataclass
class Project:
    root: Path
    actions: dict[str, ActionDefinition] = field(default_factory=dict)
    apex_targets: dict[str, TargetSignature] = field(default_factory=dict)
    flow_targets: dict[str, TargetSignature] = field(default_factory=dict)
    topics: dict[str, Topic] = field(default_factory=dict)
    planners: dict[str, PlannerBundle] = field(default_factory=dict)
    load_errors: list[LoadError] = field(default_factory=list)

    def target_for(self, action: ActionDefinition) -> TargetSignature | None:
        if action.invocation_target_type == "apex":
            return self.apex_targets.get(action.invocation_target)
        if action.invocation_target_type == "flow":
            return self.flow_targets.get(action.invocation_target)
        return None


def _text(node: ET.Element, tag: str, default: str = "") -> str:
    child = node.find(f"m:{tag}", NS)
    return (child.text or "").strip() if child is not None and child.text else default


def package_directories(root: Path) -> list[Path]:
    config = root / "sfdx-project.json"
    if not config.is_file():
        raise ProjectError(f"{root}: no sfdx-project.json; is this an SFDX project?")
    try:
        raw = json.loads(config.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectError(f"{config}: not valid JSON ({exc.msg} at line {exc.lineno})") from exc
    dirs = raw.get("packageDirectories")
    if not isinstance(dirs, list) or not dirs:
        raise ProjectError(f"{config}: packageDirectories is missing or empty")
    out = []
    for entry in dirs:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ProjectError(f"{config}: every packageDirectories entry needs a path")
        candidate = root / entry["path"]
        if not candidate.is_dir():
            raise ProjectError(f"{config}: package directory {entry['path']!r} does not exist")
        out.append(candidate)
    return out


def _load_action(folder: Path, project: Project) -> None:
    meta = folder / f"{folder.name}.genAiFunction-meta.xml"
    if not meta.is_file():
        project.load_errors.append(LoadError(str(folder), "action folder has no -meta.xml"))
        return
    try:
        root = ET.parse(meta).getroot()
    except ET.ParseError as exc:
        project.load_errors.append(LoadError(str(meta), f"not well-formed XML ({exc})"))
        return
    action = ActionDefinition(
        name=folder.name,
        path=meta,
        master_label=_text(root, "masterLabel"),
        description=_text(root, "description"),
        invocation_target=_text(root, "invocationTarget"),
        invocation_target_type=_text(root, "invocationTargetType").lower(),
        confirmation_required=_text(root, "isConfirmationRequired", "false").lower() == "true",
    )
    for kind in ("input", "output"):
        schema_path = folder / kind / "schema.json"
        if not schema_path.is_file():
            continue
        try:
            schema = load_schema(schema_path, kind)
        except SchemaError as exc:
            project.load_errors.append(LoadError(str(schema_path), str(exc)))
            continue
        if kind == "input":
            action.input_schema = schema
        else:
            action.output_schema = schema
    project.actions[action.name] = action


def load_project(root: Path) -> Project:
    """Load every agent-related piece under the project's package directories."""
    root = Path(root)
    project = Project(root=root)
    for pkg in package_directories(root):
        for folder in sorted(pkg.rglob("genAiFunctions/*")):
            if folder.is_dir():
                _load_action(folder, project)
        for cls_path in sorted(pkg.rglob("classes/*.cls")):
            try:
                parsed = apex.parse_apex(cls_path)
            except apex.ApexError as exc:
                project.load_errors.append(LoadError(str(cls_path), str(exc)))
                continue
            project.apex_targets[parsed.name] = apex.signature(parsed)
        for flow_path in sorted(pkg.rglob("flows/*.flow-meta.xml")):
            try:
                parsed_flow = flow.parse_flow(flow_path)
            except flow.FlowError as exc:
                project.load_errors.append(LoadError(str(flow_path), str(exc)))
                continue
            project.flow_targets[parsed_flow.name] = flow.signature(parsed_flow)
        for topic_path in sorted(pkg.rglob("genAiPlugins/*.genAiPlugin-meta.xml")):
            try:
                topic = parse_topic(topic_path)
            except TopicError as exc:
                project.load_errors.append(LoadError(str(topic_path), str(exc)))
                continue
            project.topics[topic.name] = topic
        for bundle_path in sorted(pkg.rglob("genAiPlannerBundles/*/*.genAiPlannerBundle-meta.xml")):
            try:
                bundle = parse_planner_bundle(bundle_path)
            except TopicError as exc:
                project.load_errors.append(LoadError(str(bundle_path), str(exc)))
                continue
            project.planners[bundle.name] = bundle
    return project
