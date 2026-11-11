"""Exit codes with a meaning a pipeline can branch on.

A linter that returns 1 for "I found drift" and 1 for "I could not read the project" teaches a
pipeline to treat a parse failure as a passing scan the moment someone adds `|| true`. These codes
keep "the tool answered no" apart from "the tool failed to answer", which is the distinction a CI
step actually needs.
"""

CLEAN = 0
"""Every action reconciled, nothing undecidable at the chosen severity."""

DRIFT_FOUND = 1
"""The tool did its job and the answer was no: at least one failing finding."""

COULD_NOT_ANSWER = 2
"""The tool failed to answer: unreadable project, malformed metadata, missing directory."""

USAGE = 3
"""Bad arguments. Nothing was examined."""

DESCRIPTIONS = {
    CLEAN: "clean: every action reconciled with its target",
    DRIFT_FOUND: "drift found: the tool answered and the answer was no",
    COULD_NOT_ANSWER: "could not answer: project unreadable or metadata malformed",
    USAGE: "usage error: nothing was examined",
}
