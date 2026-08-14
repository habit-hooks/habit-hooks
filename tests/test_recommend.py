"""Unit tests for what the plugin recommendation tells you to do.

Installing a plugin does not switch it on — a plugin runs only when the project's
``plugins`` list names it. A hint that says `pip install` to someone who has
already installed it is a loop with no exit, so each hint names the step its
reader is actually missing. Which languages count as used at all is
``docs/habit-sensors.spec.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from habit_hooks.recommend import PluginStatus, recommendations
from habit_hooks.resolve import Resolver
from plugin_fixture import write_plugin

INSTALL_AND_ENABLE = (
    "habit-sensors: detected python; consider `pip install habit-hooks-python`, "
    'then add "python" to `plugins` in .habit-hooks/config.toml'
)
ENABLE_ONLY = (
    "habit-sensors: detected python; the python plugin is installed but not "
    'enabled — add "python" to `plugins` in .habit-hooks/config.toml'
)


def _on_hand(*plugins: str) -> Callable[[str], bool]:
    return lambda name: name in plugins


def _hints(project_dir: Path, plugins: PluginStatus) -> list[str]:
    return recommendations(project_dir, ["src/app.py"], plugins)


def test_an_uninstalled_plugin_is_named_with_both_steps(tmp_path: Path) -> None:
    """Nothing to install it from and nothing enabling it: say both, once, so
    following the hint is enough — the reader is not sent back for a second line."""
    assert _hints(tmp_path, PluginStatus(set(), _on_hand())) == [INSTALL_AND_ENABLE]


def test_an_installed_but_unenabled_plugin_is_told_to_enable_it(tmp_path: Path) -> None:
    """The dead end: `pip install habit-hooks-python` has already been run, so
    repeating it is the one instruction that cannot change the outcome."""
    assert _hints(tmp_path, PluginStatus(set(), _on_hand("python"))) == [ENABLE_ONLY]


def test_an_active_language_is_not_recommended(tmp_path: Path) -> None:
    """An enabled plugin declaring the language answers for it — nothing to say."""
    assert _hints(tmp_path, PluginStatus({"python"}, _on_hand("python"))) == []


def test_an_unused_language_is_not_recommended(tmp_path: Path) -> None:
    """No `*.py` in scope and no `pyproject.toml`: no signal, no hint."""
    assert recommendations(tmp_path, ["src/app.rb"], PluginStatus(set(), _on_hand())) == []


def test_a_java_project_is_recommended_java(tmp_path: Path) -> None:
    """A `pom.xml` or `build.gradle` — the two build tools that own the
    ecosystem — counts as java, as does any `.java` file in scope."""
    (tmp_path / "pom.xml").write_text("<project/>")
    assert recommendations(tmp_path, [], PluginStatus(set(), _on_hand())) == [
        "habit-sensors: detected java; "
        "consider `pip install habit-hooks-java`, "
        'then add "java" to `plugins` in .habit-hooks/config.toml'
    ]

    (tmp_path / "pom.xml").unlink()
    (tmp_path / "build.gradle.kts").write_text("")
    assert recommendations(tmp_path, [], PluginStatus(set(), _on_hand())) != []
    assert recommendations(tmp_path, [], PluginStatus({"java"}, _on_hand("java"))) == []
    assert recommendations(tmp_path, ["src/App.java"], PluginStatus(set(), _on_hand())) != []


def test_a_vendored_plugin_counts_as_installed(tmp_path: Path) -> None:
    """``Resolver.has_plugin`` is the question, so a plugin vendored under
    ``.habit-hooks/<name>/`` — the install route the README offers where extras
    cannot reach — is on hand exactly as an installed package is, and its reader
    is told to enable it rather than to install what they already have."""
    write_plugin(tmp_path, "python", {"config.toml": 'language = "python"'})
    resolver = Resolver.discover(tmp_path)
    assert resolver.has_plugin("python")
    assert _hints(tmp_path, PluginStatus(set(), resolver.has_plugin)) == [ENABLE_ONLY]
