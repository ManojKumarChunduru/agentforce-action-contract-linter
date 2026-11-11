# ADR-003: Severity decides the exit code; evidence is a separate column

Status: accepted

## Context

A gate that fails the build on every finding is deleted or weakened within a week, and then
nothing is checked. A gate that fails on nothing is decoration. Between them is a policy, and the
policy needs a basis a reviewer can argue with.

## Decision

Every drift class carries two independent attributes.

**Severity** says what the finding means for the action: `fatal` if the action cannot run as the
metadata describes (missing target, inactive Flow, no planner-usable output, topic naming an
action that does not exist), `warn` if it runs but its contract is misdescribed (orphans,
uncovered and unenforced inputs, type mismatches, the text cap), `info` if the action is merely
dead (no topic lists it). By default only `fatal` findings produce exit code 1; `--strict`
promotes `warn` and also fails on anything undecidable.

**Evidence** says what the linter's claim about the consequence rests on: `documented` if the
GenAiFunction metadata reference states it, `inferred` if it follows from the contract and has
not been observed against an org in this repository.

The two are deliberately not the same axis. Experiment 4 publishes the table: 2 of 12 classes
rest on a documented consequence (`no_planner_output`, which the reference says makes the planner
return random responses, and `text_cap_exceeded`, a cap of 250 characters on text types), and
10 are inferred. Of the 4 fatal classes, 3 of 4 fatal classes are inferred; only 1 of the fatal
classes is documented.

The defaults are the author's reading, not a constant: `afcl policy` prints them as JSON with
the reason for each line, and `afcl lint --policy` overrides them per class. A team that treats
a weakened type as fatal, or cannot yet fix every inactive Flow, changes the file rather than
the code, and an unknown class or level in the file is refused before anything is examined.

## Alternative considered

Fail only on documented consequences. That would make `missing_target` a warning, which no
reviewer would accept: an action whose Apex class does not exist cannot run, documentation or
not. The honest position is to fail on it and say plainly that the consequence is inferred.

## Consequences

The default policy is defensible line by line, and the uncomfortable fact that most of it is
inference is in the job summary of every CI run rather than in a footnote. ADR-005 names the
one experiment that would move classes from inferred to observed.
