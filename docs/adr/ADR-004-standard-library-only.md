# ADR-004: Standard library only, argparse, no runtime dependencies

Status: accepted

## Context

The place this linter is meant to run is a CI step in a Salesforce team's pipeline, alongside
`sf project deploy`. Those runners have Python because the Salesforce CLI tooling around them
does; they rarely have a pip step, and adding one to a pipeline somebody else owns is the kind of
friction that stops a tool being adopted.

## Decision

Zero runtime dependencies. `xml.etree` for metadata, `json` for schemas, `re` for the Apex
subset, `argparse` for the command line, `dataclasses` for the models. The `dev` extra (pytest,
coverage, ruff) and the `evidence` extra (Playwright, cmarkgfm, Pillow) are for this repository's
own verification and never imported by `afcl`. `python -m afcl` works from a checkout with no
install at all.

## Alternative considered

`click` for the CLI and `rich` for the terminal table. Both would make the code shorter and the
output prettier. Rejected because every import outside the standard library is a reason a
pipeline owner can give for not running the tool, and the output already has a JSON and a
markdown form for the places where prettiness matters (the job summary).

## Consequences

The text renderer is plain, the CLI is `argparse`, and the only thing a reviewer needs to run
the fixture is a Python interpreter of version 3.11 or later. The cost is paid in `report.py`,
which hand-formats a table that `rich` would have formatted for it. This is the boring choice,
made on purpose, and recorded so nobody reopens it without reading why.
