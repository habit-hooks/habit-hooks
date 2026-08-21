"""How a fixture plugin declares the tools its sensors reach for.

A ``detectors`` entry is TOML a plugin author writes by hand, so a case that
builds one writes it as text rather than as objects: what is under test is the
run reading a plugin's own ``config.toml``, and a case constructing ``Detector``
directly would skip the very reading it is about.
"""

from __future__ import annotations

JSCPD = '{ name = "jscpd", kind = "command", install = "npm i -D jscpd" }'
PMD = '{ name = "pmd", kind = "command", install = "brew install pmd" }'
TS_MORPH = '{ name = "ts-morph", kind = "node-module", install = "npm i -D ts-morph" }'


def declaring(*detectors: str) -> str:
    """A plugin ``config.toml`` line declaring these detectors, in this order."""
    return f"detectors = [{', '.join(detectors)}]"
