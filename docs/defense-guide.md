# Defense guide: agentforce-action-contract-linter

How to talk about this repository in an interview. Every number here is checked against
`docs/metrics.json` by `tools/check_numbers.py`, so if it is in this document it is what the code
produces today.

## The thirty second version

"An Agentforce action is three files nothing joins: the action metadata names its target as a
string, the two schema files describe inputs and outputs for the planner, and the Apex or Flow
declares what it actually accepts. There is no edge in the metadata between a schema property and
the variable it describes, only a name. I built a linter that draws that edge, by name and by
type, for an SFDX project, offline, with no runtime dependencies. On a fixture org with every
drift class planted once it reports 13 findings across 12 of 17 actions, and it also reports the
2 of 17 actions are undecidable where the target's type is an SObject and nothing in the schema
could be right or wrong about it."

Then stop.

The question that usually comes next: "why does the undecidable number matter?" Answer: because
a clean report on an action the tool did not actually check is worse than no report. The linter
refuses rather than guesses, and it counts the refusals so a reviewer can see the blind spot.

## The claims, each with how it is proved

### Claim 1: the linter finds every planted drift and nothing else

- Command: `afcl lint fixture` (exit code 1) and `python experiments/exp01_drift_census.py`
- Numbers: 13 findings, 13 of 13 planted drifts matched, 0 extra. 11 with contract drift and one
  reachability finding, 3 clean actions untouched.
- If pushed: "That is a planted fixture written by me, so it proves the linter finds what I
  thought of. The resolution floor of 1/13 on this fixture means a measured zero false positives
  is a rate below one in thirteen, not zero. ADR-005 says exactly that, and the v2 list starts
  with a fixture written by someone else."

### Claim 2: a name-only review misses nearly half the findings

- Command: `python experiments/exp02_name_only_review.py`
- Numbers: a name-only review sees 7 of 13 findings; the 6 it misses (46.2% of the findings) are
  2 type mismatches, a required input that is present but unenforced, the text cap, the missing
  planner flag, and the inactive Flow.
- If pushed: "Name-only is what a pull request review actually does, and I implemented it as a
  mode of the same reconciler so the comparison is on identical input. It is not a mode the CLI
  exposes; it exists to measure the alternative I rejected in ADR-001."

### Claim 3: the tool knows what it cannot check

- Command: `python experiments/exp03_undecidable.py`
- Numbers: 2 undecidable properties out of 58 matched pairs (3.4% of matched pairs), 2 of 17
  actions are undecidable (11.8% of actions). Both are SObject typed, one on each side of the
  Apex/Flow line.
- If pushed: "Undecidable is a first class result, not an error. Under `--strict` it fails the
  build, so a team can decide whether an unchecked action is acceptable. The Apex extractor reads
  a small subset and refuses the rest, which is ADR-002; the alternative was a real parser, and
  the cost of being wrong without one is bounded by the refusal rule."

### Claim 4: the severity policy is defensible and its evidence is published

- Command: `python experiments/exp04_severity_evidence.py`, or `afcl classes`
- Numbers: 12 drift classes. 2 of 12 classes rest on a documented consequence (the planner flag,
  and the cap of 250 characters on text types); 10 are inferred. 4 fatal classes, of which 3 of 4
  fatal classes are inferred and only 1 of the fatal classes is documented.
- If pushed: "Severity is about whether the action can run; evidence is about what my claim
  rests on. I kept them apart so the exit code is defensible line by line and the thinness of
  the evidence is in the job summary rather than hidden. The scratch org experiment that would
  move classes from inferred to observed is described in ADR-005 and is out of scope because the
  repository's verification runs with no org, no credentials and no network."

### Claim 5: every number is machine checked

- Command: `make verify`
- Numbers: 250 tests, 99.5% line coverage with a 95% floor in CI, every figure in the README and
  in this guide re-measured by `tools/collect_metrics.py` and held to the prose by
  `tools/check_numbers.py`.
- If pushed: "The checker matches anchor phrases, not digits, because a digit search passes while
  the sentence around it goes stale. I proved it works by changing one figure in the README and
  watching the build fail before I trusted it."

## Questions that are meant to be hard

**Isn't this just a schema validator?** A schema validator checks a JSON file against a JSON
Schema. This checks two JSON files against an Apex signature and a Flow definition that are not
JSON and that the schema files never reference. The edge it draws does not exist in any artefact
Salesforce ships; that is the point.

**The fixture is synthetic. Does any of this transfer?** The findings transfer exactly, because
the linter reads files and a retrieve from a real org produces the same kinds of files. What does
not transfer is the consequence: whether a given drift breaks the agent at runtime is inferred for
10 of the 12 drift classes. I say so in the README, in ADR-003, in ADR-005 and in the CI summary.

**Why not just deploy and see?** Because the deploy is what cannot see it. A deploy validates
each file; the schema files are valid JSON and the Apex compiles. Nothing in the deploy pairs a
schema property with an invocable variable. Whether the deploy catches the two dangling
reference classes is the one claim I cannot make without a scratch org, and I say "the metadata
cannot see" rather than "the deploy accepts" for that reason.

**What is the weakest part?** The Apex extractor. It is regular expressions and a brace matcher
over a subset of the language, and it will miss a variable whose declaration is split in a way I
did not anticipate. I made that failure mode safe rather than impossible: a missed variable shows
up as `uncovered_input` or `orphan_input`, which is a visible false finding, not a silent pass.
The second weakest is that the fixture was written by the linter's author.

**Why Python and not Apex or Node?** It cannot be Apex: Apex runs in an org and the point is to
run before anything reaches one. Node would have worked. Python with no runtime dependencies was
chosen because the target is a CI runner next to the Salesforce CLI with no install step, and
`python -m afcl` works from a checkout with nothing installed (ADR-004).

**What would you do differently with more time?** Run the scratch org experiment first, before
writing the severity policy, so that the evidence column had `deploy_rejects` and `observed` in
it rather than only `documented` and `inferred`. Then read `GenAiPlannerBundle` local actions,
which the loader does not see today.

**How do you know the type table is right?** It is eight kinds, each with an exact set of
`lightning:type` values, tested in both directions in `tests/test_targets.py`, and the direction
labels (`weakened`, `widened`, `narrowed`) are descriptive and do not change severity. If an
entry is wrong the symptom is a false `type_mismatch`, which is a warning, not a fatal.

## Things to say and things not to say

Say:

- "13 findings across 12 of 17 actions, and 2 of 17 actions are undecidable."
- "A name-only review sees 7 of 13 findings."
- "Only 1 of the fatal classes has a documented consequence; the rest are inferred."
- "Exit code 1 means the tool answered no; exit code 2 means it could not answer."
- "Every number is re-measured by CI."

Do not say:

- "Zero false positives." Say: 13 of 13 planted drifts matched, with a resolution floor of 1/13
  on this fixture.
- "The deploy accepts this." Say: the metadata cannot see it; whether the deploy rejects any of
  it is not observed here.
- "It parses Apex." Say: it reads the invocable subset and refuses the rest.
- "It is fully tested." Say: 250 tests, 99.5% line coverage, and the untested lines are the
  `__main__` guard and one branch of the argparse exit handling.
- "It works on any org." Say: it reads any SFDX project; actions stored inside a planner bundle
  are not read yet.

## The live demo script

```bash
afcl lint fixture                                   # the verdict, the table, the findings; exit 1
afcl lint fixture --format json | head -20          # the totals a pipeline would read
python experiments/exp02_name_only_review.py        # the 6 findings a name match cannot see
python experiments/exp03_undecidable.py             # the 2 properties it cannot judge, and why
make receipts                                       # every figure re-measured and re-checked
```
