# ADR-005: What a committed fixture cannot establish

Status: accepted

## Context

Every number in this repository is reproduced offline from a committed SFDX project that has
never been deployed. That is a deliberate trade: reproducibility over realism. It is also a
boundary, and a repository that does not draw its own boundary leaves the reader to guess where
it is.

## Decision

State the boundary in three parts.

**Claims that are identical against a real org.** The linter reads metadata files and nothing
else. Whether a schema property has a matching variable, whether the types agree, whether a Flow
is marked Active, whether a topic lists an action that exists: these are facts about files, and
a retrieve from an org produces the same files. The 13 findings on the fixture are what the
linter would report on any org whose metadata looked like this.

**Claims that are declared from documentation, not observed.** The consequence of each drift
class at runtime. `no_planner_output` and `text_cap_exceeded` are documented in the GenAiFunction
metadata reference; the other 10 inferred classes follow from the contract and have not been
watched happening. The fixture cannot change that, because the fixture does not run.

**The one claim that needs a scratch org.** Which drift classes the platform's own deploy
rejects. It is likely that a topic naming a nonexistent action, or an action naming a nonexistent
class, fails validation at deploy time; it is likely that a type disagreement between a schema
and an Apex signature does not. Neither has been observed here. Until it is, the README says
"the metadata cannot see" rather than "the deploy accepts", and this ADR is where the difference
is recorded. The experiment that would close it: deploy each planted drift to a scratch org one
at a time, record which deployments fail, and move those classes to a `deploy_rejects` evidence
level. That experiment is out of scope because it needs credentials, a network and an org, all
three of which the repository's verification deliberately does without.

**A second boundary, inside the fixture.** With 13 planted drifts the ground truth match is
13 of 13 planted, and a measured zero false positives means a rate below the resolution floor
of 1/13 on this fixture, not zero. The fixture was written by the same person who wrote the
linter, so it cannot surface a drift shape that person did not think of. The decoy (a label that
differs from a title) is the only adversarial case in it.

## Consequences

The README has a section titled "What this cannot measure" that links here. The severity table
carries an evidence column rather than hiding inference behind confident wording. And the Pivot,
an `--org` mode, is listed with its trigger condition rather than built, because building it
would not change any claim in this document until the scratch org experiment is run.
