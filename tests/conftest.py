"""Shared fixtures: the committed fixture org, and a builder for small synthetic projects.

The builder writes the same file shapes the real fixture uses, so a unit test can plant one
drift in isolation and assert on exactly one finding without reading the whole org.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from afcl.contracts import reconcile
from afcl.project import load_project

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "fixture"
NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'

OBJECT = "lightning__objectType"


def input_schema(props: dict, required: list[str] | None = None) -> dict:
    return {"lightning:type": OBJECT, "required": required or [], "properties": props}


def output_schema(props: dict) -> dict:
    return {"lightning:type": OBJECT, "properties": props}


def prop(ltype: str, title: str = "x", planner: bool = False, **extra) -> dict:
    d = {"title": title, "description": title, "lightning:type": ltype}
    if planner:
        d["copilotAction:isUsedByPlanner"] = True
    d.update(extra)
    return d


SIMPLE_APEX = """
public with sharing class {name} {{
    public class Request {{
{inputs}
    }}
    public class Response {{
{outputs}
    }}
    @InvocableMethod(label='{name}')
    public static List<Response> run(List<Request> requests) {{
        return new List<Response>();
    }}
}}
"""


def apex_source(name: str, inputs: list[tuple], outputs: list[tuple]) -> str:
    """inputs/outputs are (type, name, required) or (type, name)."""

    def field(spec):
        apex_type, var_name = spec[0], spec[1]
        required = "required=true " if len(spec) > 2 and spec[2] else ""
        return (
            f"        @InvocableVariable({required}label='{var_name}')\n"
            f"        public {apex_type} {var_name};"
        )

    return SIMPLE_APEX.format(
        name=name,
        inputs="\n".join(field(s) for s in inputs),
        outputs="\n".join(field(s) for s in outputs),
    )


def flow_source(
    name: str, inputs: list[tuple], outputs: list[tuple], status: str = "Active"
) -> str:
    """inputs/outputs are (dataType, name) or (dataType, name, extra_xml)."""

    def var(spec, is_input):
        data_type, var_name = spec[0], spec[1]
        extra = spec[2] if len(spec) > 2 else ""
        return (
            "    <variables>\n"
            f"        <name>{var_name}</name>\n"
            f"        <dataType>{data_type}</dataType>\n"
            "        <isCollection>false</isCollection>\n"
            f"        <isInput>{'true' if is_input else 'false'}</isInput>\n"
            f"        <isOutput>{'false' if is_input else 'true'}</isOutput>\n"
            f"{extra}"
            "    </variables>"
        )

    body = "\n".join([var(s, True) for s in inputs] + [var(s, False) for s in outputs])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Flow {NS}>\n    <apiVersion>62.0</apiVersion>\n    <label>{name}</label>\n"
        f"    <processType>AutoLaunchedFlow</processType>\n    <status>{status}</status>\n"
        f"{body}\n</Flow>\n"
    )


class ProjectBuilder:
    def __init__(self, root: Path):
        self.root = root
        self.default = root / "force-app" / "main" / "default"
        self.default.mkdir(parents=True)
        (root / "sfdx-project.json").write_text(
            json.dumps({"packageDirectories": [{"path": "force-app", "default": True}]})
        )

    def write(self, rel: str, text: str) -> Path:
        p = self.default / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def apex(self, name: str, inputs=(), outputs=(), source: str | None = None) -> Path:
        src = source if source is not None else apex_source(name, list(inputs), list(outputs))
        self.write(
            f"classes/{name}.cls-meta.xml", f"<ApexClass {NS}><status>Active</status></ApexClass>"
        )
        return self.write(f"classes/{name}.cls", src)

    def flow(self, name: str, inputs=(), outputs=(), status="Active", source=None) -> Path:
        src = (
            source if source is not None else flow_source(name, list(inputs), list(outputs), status)
        )
        return self.write(f"flows/{name}.flow-meta.xml", src)

    def action(
        self,
        name: str,
        target: str,
        target_type: str = "apex",
        input: dict | None = None,  # noqa: A002
        output: dict | None = None,
        meta: str | None = None,
    ) -> Path:
        xml = meta or (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"<GenAiFunction {NS}>\n    <description>{name}</description>\n"
            f"    <invocationTarget>{target}</invocationTarget>\n"
            f"    <invocationTargetType>{target_type}</invocationTargetType>\n"
            f"    <masterLabel>{name}</masterLabel>\n</GenAiFunction>\n"
        )
        p = self.write(f"genAiFunctions/{name}/{name}.genAiFunction-meta.xml", xml)
        if input is not None:
            self.write(f"genAiFunctions/{name}/input/schema.json", json.dumps(input))
        if output is not None:
            self.write(f"genAiFunctions/{name}/output/schema.json", json.dumps(output))
        return p

    def topic(self, name: str, functions=(), instructions=1) -> Path:
        fns = "".join(
            f"    <genAiFunctions>\n        <functionName>{f}</functionName>\n"
            "    </genAiFunctions>\n"
            for f in functions
        )
        ins = "".join(
            f"    <genAiPluginInstructions>\n        <description>i{i}</description>\n"
            f"        <developerName>{name}_i{i}</developerName>\n"
            f"        <masterLabel>i{i}</masterLabel>\n    </genAiPluginInstructions>\n"
            for i in range(instructions)
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"<GenAiPlugin {NS}>\n    <developerName>{name}</developerName>\n{fns}{ins}"
            f"    <language>en_US</language>\n    <masterLabel>{name}</masterLabel>\n"
            "    <pluginType>Topic</pluginType>\n</GenAiPlugin>\n"
        )
        return self.write(f"genAiPlugins/{name}.genAiPlugin-meta.xml", xml)

    def planner(self, name: str, topics=()) -> Path:
        plugins = "".join(
            f"    <genAiPlugins>\n        <genAiPluginName>{t}</genAiPluginName>\n"
            "    </genAiPlugins>\n"
            for t in topics
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"<GenAiPlannerBundle {NS}>\n{plugins}    <masterLabel>{name}</masterLabel>\n"
            "</GenAiPlannerBundle>\n"
        )
        return self.write(f"genAiPlannerBundles/{name}/{name}.genAiPlannerBundle-meta.xml", xml)

    def load(self):
        return load_project(self.root)

    def report(self, **kwargs):
        return reconcile(self.load(), **kwargs)


@pytest.fixture
def builder(tmp_path: Path) -> ProjectBuilder:
    return ProjectBuilder(tmp_path / "proj")


@pytest.fixture(scope="session")
def fixture_project():
    return load_project(FIXTURE_ROOT)


@pytest.fixture(scope="session")
def fixture_report(fixture_project):
    return reconcile(fixture_project)


@pytest.fixture(scope="session")
def expected():
    return json.loads((FIXTURE_ROOT / "EXPECTED_DRIFTS.json").read_text())
