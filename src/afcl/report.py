"""Rendering a LintReport for the three places it gets read.

A terminal (text), a pipeline (JSON), a pull request or job summary (markdown), and a browser
(HTML, which is also what the committed screenshot is taken from). Every renderer reads the same
report object, so the number in the job summary is the number in the JSON, and neither can drift
from the other. The HTML keeps its CSS inline and its headings named, because the screenshot tool
frames by heading and reads the verdict badge's computed colour back (see
`tools/capture_screenshots.py`).
"""

from __future__ import annotations

import html
import json
from dataclasses import asdict

from afcl.contracts import DRIFT_CLASSES, FATAL, INFO, WARN, LintReport

_SEVERITY_ORDER = {FATAL: 0, WARN: 1, INFO: 2}


def verdict(report: LintReport, strict: bool) -> str:
    if report.should_fail(strict):
        return "DRIFT"
    if report.undecidables:
        return "CLEAN WITH GAPS"
    return "CLEAN"


def _sorted_findings(report: LintReport):
    return sorted(
        report.findings,
        key=lambda f: (_SEVERITY_ORDER[f.severity], f.drift_class, f.action, f.property_name),
    )


def summary_rows(report: LintReport) -> list[tuple[str, str, str, int]]:
    """(class, severity, evidence, count) for every drift class, zeros included."""
    counts = report.by_class()
    rows = []
    for name, dc in DRIFT_CLASSES.items():
        rows.append((name, dc.severity, dc.evidence, counts.get(name, 0)))
    rows.sort(key=lambda r: (_SEVERITY_ORDER[r[1]], r[0]))
    return rows


def to_dict(report: LintReport, strict: bool = False) -> dict:
    return {
        "verdict": verdict(report, strict),
        "strict": strict,
        "name_only": report.name_only,
        "policy": {
            "severity_overrides": dict(report.policy.severity),
            "fail_on_undecidable": report.policy.fail_on_undecidable,
        },
        "totals": {
            "actions": report.actions_total,
            "topics": report.topics_total,
            "planners": report.planners_total,
            "findings": len(report.findings),
            "actions_with_findings": len(report.actions_with_findings()),
            "undecidable_properties": len(report.undecidables),
            "actions_undecidable": len(report.actions_undecidable()),
        },
        "by_class": dict(sorted(report.by_class().items())),
        "by_severity": dict(sorted(report.by_severity().items())),
        "by_target_type": dict(sorted(report.by_target_type().items())),
        "findings": [asdict(f) for f in _sorted_findings(report)],
        "undecidable": [asdict(u) for u in report.undecidables],
    }


def to_json(report: LintReport, strict: bool = False) -> str:
    return json.dumps(to_dict(report, strict), indent=2, sort_keys=False) + "\n"


def to_text(report: LintReport, strict: bool = False) -> str:
    lines = [
        f"agentforce action contract linter: {verdict(report, strict)}",
        f"  actions {report.actions_total}, topics {report.topics_total}, "
        f"planners {report.planners_total}" + (", mode strict" if strict else ""),
        f"  findings {len(report.findings)} across "
        f"{len(report.actions_with_findings())} actions; "
        f"undecidable properties {len(report.undecidables)} across "
        f"{len(report.actions_undecidable())} actions",
        "",
        f"  {'class':<26} {'severity':<9} {'evidence':<11} count",
    ]
    for name, sev, ev, count in summary_rows(report):
        lines.append(f"  {name:<26} {sev:<9} {ev:<11} {count}")
    if report.findings:
        lines.append("")
        lines.append("findings")
        for f in _sorted_findings(report):
            tail = f" ({f.detail})" if f.detail else ""
            lines.append(f"  [{f.severity:<5}] {f.drift_class:<24} {f.action}: {f.message}{tail}")
    if report.undecidables:
        lines.append("")
        lines.append("undecidable (not checked, not counted as drift)")
        for u in report.undecidables:
            lines.append(f"  {u.action}.{u.variable} ({u.side}, {u.declared_type}): {u.reason}")
    return "\n".join(lines) + "\n"


def to_markdown(report: LintReport, strict: bool = False) -> str:
    lines = [
        f"## Agentforce action contract linter: {verdict(report, strict)}",
        "",
        f"{report.actions_total} actions, {report.topics_total} topics, "
        f"{len(report.findings)} findings across {len(report.actions_with_findings())} actions, "
        f"{len(report.undecidables)} undecidable properties across "
        f"{len(report.actions_undecidable())} actions.",
        "",
        "| class | severity | evidence | count |",
        "| --- | --- | --- | --- |",
    ]
    for name, sev, ev, count in summary_rows(report):
        lines.append(f"| {name} | {sev} | {ev} | {count} |")
    if report.findings:
        lines += ["", "| severity | class | action | message |", "| --- | --- | --- | --- |"]
        for f in _sorted_findings(report):
            msg = f.message.replace("|", "\\|")
            lines.append(f"| {f.severity} | {f.drift_class} | {f.action} | {msg} |")
    if report.undecidables:
        lines += [
            "",
            "| action | variable | side | declared type | reason |",
            "| --- | --- | --- | --- | --- |",
        ]
        for u in report.undecidables:
            lines.append(
                f"| {u.action} | {u.variable} | {u.side} | {u.declared_type} | {u.reason} |"
            )
    return "\n".join(lines) + "\n"


_CSS = """
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; margin: 2rem;
       color: #1f2328; background: #ffffff; max-width: 960px; }
h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #d0d7de;
     padding-bottom: 0.25rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid #eaeef2; }
th { background: #f6f8fa; }
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 0.4rem; font-weight: 700;
         color: #ffffff; background: #6e7781; }
.badge-drift { background: #cf222e; }
.badge-clean { background: #1a7f37; }
.badge-gaps { background: #9a6700; }
.sev-fatal { color: #cf222e; font-weight: 600; }
.sev-warn { color: #9a6700; font-weight: 600; }
.sev-info { color: #6e7781; }
.muted { color: #6e7781; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85em; }
"""

_BADGE_CLASS = {"DRIFT": "badge-drift", "CLEAN": "badge-clean", "CLEAN WITH GAPS": "badge-gaps"}


def to_html(report: LintReport, strict: bool = False) -> str:
    v = verdict(report, strict)
    e = html.escape
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<title>Agentforce action contract report</title>",
        f"<style>{_CSS}</style></head><body>",
        "<h1>Agentforce action contract report</h1>",
        f"<p><span class='badge {_BADGE_CLASS[v]}'>{e(v)}</span> "
        f"<span class='muted'>{report.actions_total} actions, {report.topics_total} topics, "
        f"{len(report.findings)} findings across {len(report.actions_with_findings())} actions, "
        f"{len(report.undecidables)} undecidable properties"
        f"{', strict' if strict else ''}</span></p>",
        "<h2 id='summary'>Summary by drift class</h2>",
        "<table><thead><tr><th>class</th><th>severity</th><th>evidence</th><th>count</th></tr>"
        "</thead><tbody>",
    ]
    for name, sev, ev, count in summary_rows(report):
        parts.append(
            f"<tr><td><code>{e(name)}</code></td><td class='sev-{sev}'>{sev}</td>"
            f"<td>{ev}</td><td>{count}</td></tr>"
        )
    parts.append("</tbody></table>")
    parts.append("<h2 id='findings'>Findings</h2>")
    if report.findings:
        parts.append(
            "<table><thead><tr><th>severity</th><th>class</th><th>action</th><th>message</th>"
            "</tr></thead><tbody>"
        )
        for f in _sorted_findings(report):
            tail = f" <span class='muted'>({e(f.detail)})</span>" if f.detail else ""
            parts.append(
                f"<tr><td class='sev-{f.severity}'>{f.severity}</td>"
                f"<td><code>{e(f.drift_class)}</code></td><td>{e(f.action)}</td>"
                f"<td>{e(f.message)}{tail}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p class='muted'>None.</p>")
    parts.append("<h2 id='undecidable'>Undecidable: checked by nobody</h2>")
    if report.undecidables:
        parts.append(
            "<table><thead><tr><th>action</th><th>variable</th><th>side</th>"
            "<th>declared type</th><th>reason</th></tr></thead><tbody>"
        )
        for u in report.undecidables:
            parts.append(
                f"<tr><td>{e(u.action)}</td><td><code>{e(u.variable)}</code></td>"
                f"<td>{e(u.side)}</td><td><code>{e(u.declared_type)}</code></td>"
                f"<td>{e(u.reason)}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p class='muted'>None.</p>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


RENDERERS = {"text": to_text, "json": to_json, "markdown": to_markdown, "html": to_html}
