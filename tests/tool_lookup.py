"""An environment in which a wrapped tool's bare name reaches nothing.

A sensor is handed the file this project runs for each tool its recipe names,
and spawning that file rather than the name it was resolved from is the whole of
what the sensor owes. The way to prove a helper does it is to take the name away
and watch the tool still run — which is what this builds.

It lives here, one home for four plugin suites, because the alternative is what
this whole arrangement replaced: a copy per plugin, drifting quietly, with the
one spelling that fails on Windows indistinguishable from the three that do not.
A plugin's *shipped* code may not import the core (each declares
``dependencies = []``), but its tests are never shipped — ``packages`` names only
the import package — and they run from this repo, whose ``pythonpath`` puts this
directory on the path for every test in the run.
"""

from __future__ import annotations

import os
import shutil


def where_the_bare_name_reaches_nothing(name: str) -> dict[str, str]:
    """This machine's environment, minus every directory that answers ``name``.

    Only those directories go. A wrapped tool is rarely a program on its own —
    jscpd reaches for node, PMD for a JVM, php for its own ini and extensions —
    so emptying the environment outright would fail a sensor that did everything
    right, and on Windows would take ``SYSTEMROOT``, ``TEMP`` and ``APPDATA``
    with it. Every such directory rather than the first, because a machine may
    have the tool installed twice.

    What is left cannot answer the bare name, and that is asserted rather than
    assumed: ``PATH`` is not the whole of where a spawn looks on Windows, which
    is the platform this is about.
    """
    path = os.pathsep.join(
        entry
        for entry in os.environ["PATH"].split(os.pathsep)
        if shutil.which(name, path=entry) is None
    )
    assert shutil.which(name, path=path) is None, f"{name} is still on the path"
    return {**os.environ, "PATH": path}
