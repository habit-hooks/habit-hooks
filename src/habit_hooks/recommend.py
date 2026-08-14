"""Recommend a plugin for a language the project uses but has no active plugin for.

A non-fatal hint printed to stderr only: it never changes the findings output or
the exit code. Detection is deliberately conservative — a language counts as used
only on a cheap, clear signal (a known config file in the project root or a file
extension among the scoped files). A language whose plugin already declares it is
never recommended.

Installing a plugin does not switch it on: it runs only once the project's
``plugins`` list names it. So the hint names the step its reader is actually
missing — a reader who has the plugin is told to enable it, never to install
what they already have.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LanguageSignal:
    language: str
    config_files: tuple[str, ...]
    extensions: tuple[str, ...]


LANGUAGE_SIGNALS = (
    LanguageSignal("python", ("pyproject.toml",), (".py",)),
    LanguageSignal("typescript", ("tsconfig.json",), (".ts", ".tsx")),
    LanguageSignal("php", ("composer.json",), (".php",)),
)


@dataclass(frozen=True)
class PluginStatus:
    """What the run already covers, and how to ask whether a plugin is on hand.

    ``is_installed`` is the resolver's own question (``Resolver.has_plugin``), so
    a plugin vendored under ``.habit-hooks/<name>/`` counts as on hand exactly as
    an installed package does — a hint must never tell someone to install what
    they have. It is asked by plugin name, which for every recommendable language
    is the language itself, as ``pip install habit-hooks-<language>`` already
    assumes.
    """

    active_languages: set[str]
    is_installed: Callable[[str], bool]


def _is_used(signal: LanguageSignal, project_dir: Path, files: list[str]) -> bool:
    if any((project_dir / name).is_file() for name in signal.config_files):
        return True
    return any(file.endswith(signal.extensions) for file in files)


def _enable(language: str) -> str:
    return f'add "{language}" to `plugins` in .habit-hooks/config.toml'


def _hint(language: str, plugins: PluginStatus) -> str:
    """The one line for this language: the step its reader is missing.

    Enabling is named either way, so following the hint once is enough. Naming
    only the install left a reader who ran it facing the same line again, with
    nothing in it that could change the outcome.
    """
    if plugins.is_installed(language):
        return (
            f"habit-sensors: detected {language}; the {language} plugin is "
            f"installed but not enabled — {_enable(language)}"
        )
    return (
        f"habit-sensors: detected {language}; "
        f"consider `pip install habit-hooks-{language}`, then {_enable(language)}"
    )


def used_languages(project_dir: Path, files: list[str]) -> list[str]:
    """Every language the project shows a signal for, in the table's own order.

    The one answer to "what is this project written in": the hint below asks it
    of a run's scoped files, and setting a project up asks it of the project's
    own files, so a language init plans a plugin for is a language a run would
    have recommended one for.
    """
    return [
        signal.language
        for signal in LANGUAGE_SIGNALS
        if _is_used(signal, project_dir, files)
    ]


def recommendations(
    project_dir: Path, files: list[str], plugins: PluginStatus
) -> list[str]:
    """Hint lines for used languages no active plugin covers, one per language."""
    return [
        _hint(language, plugins)
        for language in used_languages(project_dir, files)
        if language not in plugins.active_languages
    ]
