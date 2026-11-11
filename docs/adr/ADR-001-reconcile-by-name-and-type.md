# ADR-001: Reconcile by name and type, not by name alone

Status: accepted

## Context

An Agentforce action's contract lives in two places that nothing joins: `input/schema.json` and
`output/schema.json` on the planner's side, and `@InvocableVariable` fields or Flow variables on
the target's side. A pull request review reconciles them the only way a human can at speed: by
reading property names on both sides and checking they line up. That is a name-only
reconciliation, and it is what this linter would have been if it had stopped at the obvious.

## Decision

Pair properties by name, then check three more things on every pair: the type (through a small
compatibility table in `targets.py` that also names the direction of a disagreement), the
required-ness for Apex (which declares it) and the declared text cap. Also check the properties
that have no pair at all, in both directions, and the planner flag on outputs.

## Alternative considered

Name-only reconciliation. It is cheaper to write, has no type table to maintain, and cannot be
wrong about a type because it never looks at one. Experiment 2 runs exactly that mode over the
fixture (`reconcile(project, name_only=True)`, which the CLI does not expose) so the cost of the
alternative is a measured number rather than an argument: a name-only review sees 7 of 13
findings on the fixture. The 6 it misses (46.2% of the findings) are the
`type_mismatch` pairs, the required variable that is present but not enforced, the text cap, the
missing planner flag and the inactive Flow. Every one of those has the right names on both sides.

## Consequences

The type table is a liability the linter has to carry: a wrong entry produces a false
`type_mismatch`. It is small (eight kinds), tested exhaustively in `tests/test_targets.py`, and
it refuses rather than guesses when a type is outside it (ADR-002). The direction label
(`weakened`, `widened`, `narrowed`, `different`) is descriptive only and does not change
severity, because the runtime consequence of each direction is inferred, not documented
(ADR-003).
