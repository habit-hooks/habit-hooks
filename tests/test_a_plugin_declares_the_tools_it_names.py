"""Every tool a shipped sensor names is declared by the plugin that ships it.

``${detector:<name>}`` is resolved against the whole run's declarations — every
active plugin's — because that is the same list a setup clears a project's tools
against, and because a root transformer has no plugin of its own to ask
(``loader.PluginLoader._with_its_tools``). The cost is that a plugin naming a
tool it forgot to declare still runs wherever another enabled plugin declares it.
Every gate in this repo runs several plugins at once, so none of them would ever
notice; the consumer who enables that one plugin meets it as a whole run stopping
at exit 2. This is what notices instead, against each plugin's own config.toml.
"""

from __future__ import annotations

import re
from pathlib import Path

from habit_hooks.config_schema import read_toml

REPO_ROOT = Path(__file__).resolve().parents[1]
DETECTOR = re.compile(r"\$\{detector:([^{}]*)\}")


def _recipe_text(spec: Path) -> str:
    """The part's recipe, whichever of the two forms it spells."""
    parsed = read_toml(spec)
    return parsed.get("command") or " ".join(parsed.get("argv", []))


def _declared_by(plugin_package: Path) -> set[str]:
    """The tools that plugin's own ``config.toml`` says its sensors reach for."""
    config = read_toml(plugin_package / "config.toml")
    return {entry["name"] for entry in config.get("detectors", [])}


def test_no_shipped_sensor_names_a_tool_its_own_plugin_left_undeclared() -> None:
    specs = sorted(REPO_ROOT.glob("plugins/*/src/habit_hooks_*/sensors/*.toml"))
    assert specs, "no shipped sensor specs found — the glob has gone stale"

    undeclared = sorted(
        f"{spec.relative_to(REPO_ROOT)} names {name!r}"
        for spec in specs
        for name in DETECTOR.findall(_recipe_text(spec))
        if name not in _declared_by(spec.parent.parent)
    )

    assert undeclared == []
