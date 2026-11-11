"""Tests that pin bugs actually hit during the build, each with the story of how it showed up."""

import builtins
import dataclasses

from afcl.contracts import Finding


def test_the_finding_dataclass_does_not_shadow_the_property_builtin():
    """The first version of Finding had a field named `property`, for the schema property name.

    Inside a class body a dataclass field is an ordinary class attribute, so the line
    `property: str = ""` rebound the name `property` to the empty string before the
    `@property` decorator on `severity` was evaluated. Importing the module raised
    `TypeError: 'str' object is not callable`, from a line that looked completely innocent.
    The field is now `property_name`, and this test keeps it that way: it fails if any
    field of Finding is named after a builtin, whatever the class body happens to rely on.
    """
    names = {f.name for f in dataclasses.fields(Finding)}
    assert "property" not in names and "property_name" in names
    assert not names & set(dir(builtins)), names & set(dir(builtins))
    assert Finding("orphan_input", "Act", "m").severity == "warn"
