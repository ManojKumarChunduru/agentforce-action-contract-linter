# ADR-002: A purpose-built extractor for the invocable subset of Apex, not a parser

Status: accepted

## Context

The linter needs five things from an Apex class: whether it carries an `@InvocableMethod`, the
request type of that method, which fields of the request class carry `@InvocableVariable`, which
of those are required, and the fields of the response class. A full Apex grammar would provide
all of that and several thousand productions the linter would never read.

## Decision

`apex.py` strips comments, blanks string literals so a brace inside one cannot unbalance the
class, matches class declarations by brace matching, and reads annotations with two regular
expressions. It maps a small set of declared types to reconciler kinds (`String`, `Id`,
`Integer`, `Long`, `Decimal`, `Double`, `Boolean`, `Date`, `Datetime`, `List<>`, `Set<>`,
arrays) and refuses everything else: an SObject, a `Map`, an `Object`, a `Blob` or a custom
Apex type comes back as `undecidable` with a reason. The reconciler counts those apart from
drift, and `--strict` fails on them.

The same rule applies to shapes the extractor does not understand: a method with two parameters,
a request that is not `List<Something>`, a primitive list request. Each is reported with a note,
and the action is never marked clean on the strength of a shape the extractor could not read.

## Alternative considered

A real parser (there are open source Apex grammars for ANTLR). Rejected for this repository
because the subset is small and stable, the parser would be the largest dependency in a tool
whose deployment target is a CI step with no install (ADR-004), and the cost of being wrong is
bounded by the refusal rule. The refusal rule is the whole point: a linter that silently maps
`Contact` to text produces a clean report for a property it did not check.

## Consequences

The boundary is visible in the numbers. On the fixture, 2 of 58 matched pairs are undecidable
(3.4% of matched pairs), both SObject typed, and 2 of 17 actions are undecidable as a result.
Experiment 3 publishes that share, and the README leads with it, because the blind spot of the
tool is the first thing a reviewer should know. A constructs list the extractor is known not to
handle: inner classes nested more than one level, annotations split across lines with comments
between the annotation and the field, and `@InvocableVariable` on a property with a getter. Each
would surface as a missing variable rather than a wrong one.
