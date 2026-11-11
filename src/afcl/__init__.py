"""afcl: the Agentforce action contract linter.

Reads an SFDX project and draws the edge the metadata does not have, from each action's
schema.json files to the invocable Apex or Flow named by its invocationTarget.
"""

__version__ = "0.1.0"
