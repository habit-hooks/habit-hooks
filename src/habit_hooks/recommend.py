
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
    LanguageSignal("java", ("pom.xml", "build.gradle", "build.gradle.kts"), (".java",)),
    LanguageSignal("ruby", ("Gemfile", ".rubocop.yml"), (".rb",)),
)


@dataclass(frozen=True)
class PluginStatus:

    active_languages: set[str]
    is_installed: Callable[[str], bool]


DEPENDENCY_DIRECTORIES = frozenset(
    {"node_modules", "vendor", "site-packages", ".venv", "venv"}
)


def _inside_dependency_directory(path: str) -> bool:
    return any(part in DEPENDENCY_DIRECTORIES for part in path.split("/")[:-1])


def _is_used(signal: LanguageSignal, project_dir: Path, files: list[str]) -> bool:
    if any((project_dir / name).is_file() for name in signal.config_files):
        return True
    return any(
        file.endswith(signal.extensions) and not _inside_dependency_directory(file)
        for file in files
    )


def _enable(language: str) -> str:
    return f'add "{language}" to `plugins` in .habit-hooks/config.toml'


def _hint(language: str, plugins: PluginStatus) -> str:
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
    return [
        signal.language
        for signal in LANGUAGE_SIGNALS
        if _is_used(signal, project_dir, files)
    ]


def recommendations(
    project_dir: Path, files: list[str], plugins: PluginStatus
) -> list[str]:
    return [
        _hint(language, plugins)
        for language in used_languages(project_dir, files)
        if language not in plugins.active_languages
    ]
