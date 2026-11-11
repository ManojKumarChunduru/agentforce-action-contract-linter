"""The command line: `afcl lint <project>` and `afcl classes`.

argparse and nothing else, by decision (ADR-004): the linter is meant to be dropped into a CI
step that has Python and no pip step, so the command line cannot pull in a framework. The CLI is
deliberately thin. It parses arguments, loads the project, calls the reconciler, picks a
renderer and maps the result to an exit code; every decision that matters lives in `contracts.py`
where it is tested without a subprocess.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from afcl import exit_codes
from afcl.contracts import (
    DRIFT_CLASSES,
    Policy,
    PolicyError,
    default_policy_document,
    load_policy,
    reconcile,
)
from afcl.project import ProjectError, load_project
from afcl.report import RENDERERS, verdict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="afcl",
        description=(
            "Reconcile Agentforce action schemas against the invocable Apex or Flow behind them."
        ),
        epilog=(
            "exit codes: 0 clean, 1 drift found (the tool answered no), "
            "2 could not answer (project unreadable), 3 usage"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help="reconcile every action in an SFDX project")
    lint.add_argument("project", type=Path, help="directory containing sfdx-project.json")
    lint.add_argument(
        "--format",
        choices=sorted(RENDERERS),
        default="text",
        help="output format (default: text)",
    )
    lint.add_argument(
        "--strict",
        action="store_true",
        help="also fail on warn-level findings and on undecidable properties",
    )
    lint.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write the report to this file instead of stdout",
    )
    lint.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="JSON file overriding drift class severities (see `afcl policy`)",
    )
    lint.add_argument(
        "--allow-load-errors",
        action="store_true",
        help="report on what loaded even if some files were unreadable (exit code still 2)",
    )

    classes = sub.add_parser("classes", help="list the drift classes, their severity and evidence")
    classes.add_argument("--format", choices=["text", "markdown"], default="text")

    sub.add_parser("policy", help="print the default severity policy as JSON, with reasons")
    return parser


def _render_classes(fmt: str) -> str:
    if fmt == "markdown":
        lines = [
            "| class | severity | evidence | what it means | consequence |",
            "| --- | --- | --- | --- | --- |",
        ]
        for dc in DRIFT_CLASSES.values():
            lines.append(
                f"| {dc.name} | {dc.severity} | {dc.evidence} | {dc.summary} | {dc.consequence} |"
            )
        return "\n".join(lines) + "\n"
    lines = []
    for dc in DRIFT_CLASSES.values():
        lines.append(f"{dc.name} [{dc.severity}, {dc.evidence}]")
        lines.append(f"  {dc.summary}")
        lines.append(f"  consequence: {dc.consequence}")
    return "\n".join(lines) + "\n"


def _read_policy(path: Path | None) -> Policy:
    if path is None:
        return Policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"policy file {path} does not exist") from exc
    except json.JSONDecodeError as exc:
        raise PolicyError(f"policy file {path} is not valid JSON ({exc.msg})") from exc
    return load_policy(raw)


def run_lint(args: argparse.Namespace, out=sys.stdout, err=sys.stderr) -> int:
    try:
        policy = _read_policy(args.policy)
    except PolicyError as exc:
        print(f"afcl: {exc}", file=err)
        return exit_codes.USAGE
    try:
        project = load_project(args.project)
    except ProjectError as exc:
        print(f"afcl: could not read project: {exc}", file=err)
        return exit_codes.COULD_NOT_ANSWER
    if project.load_errors and not args.allow_load_errors:
        print(
            f"afcl: {len(project.load_errors)} file(s) could not be read; "
            "no report produced (use --allow-load-errors to report on the rest):",
            file=err,
        )
        for le in project.load_errors:
            print(f"  {le.path}: {le.message}", file=err)
        return exit_codes.COULD_NOT_ANSWER
    report = reconcile(project, policy=policy)
    rendered = RENDERERS[args.format](report, strict=args.strict)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"afcl: {verdict(report, args.strict)}; report written to {args.output}", file=err)
    else:
        out.write(rendered)
    if project.load_errors:
        for le in project.load_errors:
            print(f"afcl: unreadable: {le.path}: {le.message}", file=err)
        return exit_codes.COULD_NOT_ANSWER
    if report.should_fail(args.strict):
        return exit_codes.DRIFT_FOUND
    return exit_codes.CLEAN


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 2 on bad usage and 0 on --help; keep usage distinct from "could not answer"
        return exit_codes.USAGE if exc.code not in (0, None) else 0
    if args.command == "classes":
        sys.stdout.write(_render_classes(args.format))
        return exit_codes.CLEAN
    if args.command == "policy":
        sys.stdout.write(json.dumps(default_policy_document(), indent=2) + "\n")
        return exit_codes.CLEAN
    return run_lint(args)


if __name__ == "__main__":
    sys.exit(main())
