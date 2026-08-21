"""The shipped knip config overlooks habit-hooks' footprint — all of it, and nothing else.

A project installs the packages habit-hooks tells it to, imports none of them
because habit-hooks is what uses them, and knip then reports every one as an
unused dependency (#143). The answer is ``ignoreDependencies`` in the
typescript plugin's shipped ``knip.json``, and this is what keeps that list
honest in both directions.

**Complete**, or the bug comes back one package at a time: a plugin that grows
a ``node-module`` detector, or a shipped eslint config that grows a plugin,
adds a package to every consumer's manifest, and nobody adding one has any
reason to open ``knip.json``.

**Minimal**, or the smell quietly stops working: a name in that list is a name
no project is ever told about again, so one that is not our footprint suppresses
a finding the project needed. That drift is invisible to the plugin's own
behaviour suite, which only ever sees the packages its fixture plants.

It lives here rather than in the typescript plugin's suite for the reason
``test_a_plugin_declares_the_tools_it_names.py`` does: the answer is derived
from *every* plugin's declarations, not one plugin's. jscpd is the case that
makes that concrete — it is the **generic** plugin's detector, but knip is what
reads ``package.json`` and knip belongs to the typescript plugin, so the only
config that can name jscpd is a config in a different plugin from the one that
asked for it. A gate inside either plugin's suite could only ever see half of
that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from habit_hooks.config_schema import read_toml

REPO_ROOT = Path(__file__).resolve().parents[1]
TYPESCRIPT = REPO_ROOT / "plugins" / "typescript" / "src" / "habit_hooks_typescript"
SHIPPED_KNIP_CONFIG = TYPESCRIPT / "knip.json"
SHIPPED_ESLINT_CONFIG = TYPESCRIPT / "eslint.config.mjs"

# How a plugin spells "this one lands in the project's package.json".
NPM_INSTALL = "npm install"

# A `node-module` detector is always an npm package; a `command` detector may
# be one too (jscpd is spawned by name and still installed with npm), and node
# itself is neither. So the question is the install line, with the kind as a
# belt-and-braces second answer — a node-module that forgot its install line
# would otherwise slip past.
NODE_MODULE = "node-module"

# What the shipped eslint config asks the *project* to have installed, spelled
# as `required("<package>")` so it can say so itself when the package is absent
# (`eslint.config.mjs`, MISSING_TYPESCRIPT_ESLINT).
REQUIRED_PACKAGE = re.compile(r'required\(\s*"([^"]+)"\s*\)')

# knip leaves itself out of its own answer, so naming it would be a line that
# can never do anything — and a list carrying dead entries is a list nobody
# trusts to be minimal. (Confirmed against knip 5.88.1, which also excludes
# `typescript`; that one is nobody's detector, so it never reaches this set.)
KNIP_EXCLUDES_ITSELF = "knip"


def _packages_a_plugin_asks_for(config: Path) -> set[str]:
    return {
        detector["name"]
        for detector in read_toml(config).get("detectors", [])
        if detector.get("kind") == NODE_MODULE
        or detector.get("install", "").startswith(NPM_INSTALL)
    }


def _our_footprint_in_a_project() -> set[str]:
    """Every package habit-hooks asks a project to install."""
    configs = sorted(REPO_ROOT.glob("plugins/*/src/habit_hooks_*/config.toml"))
    assert configs, "no shipped plugin configs found — the glob has gone stale"

    declared = set().union(*(_packages_a_plugin_asks_for(one) for one in configs))
    required = set(
        REQUIRED_PACKAGE.findall(SHIPPED_ESLINT_CONFIG.read_text(encoding="utf-8"))
    )
    assert required, "the shipped eslint config named nothing — the pattern has gone stale"
    return (declared | required) - {KNIP_EXCLUDES_ITSELF}


def test_the_shipped_config_overlooks_our_footprint_and_only_our_footprint() -> None:
    shipped = json.loads(SHIPPED_KNIP_CONFIG.read_text(encoding="utf-8"))

    assert sorted(shipped["ignoreDependencies"]) == sorted(_our_footprint_in_a_project())
