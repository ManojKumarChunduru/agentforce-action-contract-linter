"""Topics and the agent that owns them: the graph that decides whether an action is reachable.

A `GenAiPlugin` (a topic) lists the actions it may call by `functionName`; a `GenAiPlannerBundle`
(the agent) lists the topics it owns. The planner never sees an action that no topic lists, so a
perfectly reconciled action with no topic is dead metadata, and a topic naming an action that does
not exist is a promise the planner cannot keep. Both are reported, but they are reported as
reachability findings, separately from contract drift, because a reviewer fixes them in a different
file.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

NS = {"m": "http://soap.sforce.com/2006/04/metadata"}
_META = "{http://soap.sforce.com/2006/04/metadata}"


class TopicError(ValueError):
    """The file could not be read as a topic or planner bundle."""


@dataclass
class Topic:
    name: str
    path: Path
    master_label: str = ""
    description: str = ""
    scope: str = ""
    functions: list[str] = field(default_factory=list)
    instruction_count: int = 0
    can_escalate: bool = False


@dataclass
class PlannerBundle:
    name: str
    path: Path
    master_label: str = ""
    topics: list[str] = field(default_factory=list)


def _text(node: ET.Element, tag: str, default: str = "") -> str:
    child = node.find(f"m:{tag}", NS)
    return (child.text or "").strip() if child is not None and child.text else default


def _root(path: Path, expected: str) -> ET.Element:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise TopicError(f"{path}: not well-formed XML ({exc})") from exc
    if root.tag != _META + expected:
        raise TopicError(f"{path}: root element is not {expected}")
    return root


def parse_topic(path: Path) -> Topic:
    root = _root(path, "GenAiPlugin")
    name = _text(root, "developerName") or path.name.split(".")[0]
    topic = Topic(
        name=name,
        path=path,
        master_label=_text(root, "masterLabel"),
        description=_text(root, "description"),
        scope=_text(root, "scope"),
        can_escalate=_text(root, "canEscalate", "false").lower() == "true",
    )
    for fn in root.findall("m:genAiFunctions", NS):
        function_name = _text(fn, "functionName")
        if function_name:
            topic.functions.append(function_name)
    topic.instruction_count = len(root.findall("m:genAiPluginInstructions", NS))
    return topic


def parse_planner_bundle(path: Path) -> PlannerBundle:
    root = _root(path, "GenAiPlannerBundle")
    bundle = PlannerBundle(
        name=path.name.split(".")[0],
        path=path,
        master_label=_text(root, "masterLabel"),
    )
    for plugin in root.findall("m:genAiPlugins", NS):
        plugin_name = _text(plugin, "genAiPluginName")
        if plugin_name:
            bundle.topics.append(plugin_name)
    return bundle


def reachable_actions(topics: dict[str, Topic]) -> set[str]:
    """Every action at least one topic lists."""
    return {fn for topic in topics.values() for fn in topic.functions}
