"""Turn one finding into the coaching text the mapper prints.

Guide resolution, severity, and the two render paths (a Jinja2 ``.md`` template
or a configured fix runner) live here; :mod:`habit_hooks.mapper` owns the stage
around them — reading stdin, ordering the blocks, and the exit code.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from jinja2 import Environment, FunctionLoader

from .catalogue import DEFAULT_SEVERITY, ENFORCED, UNCOACHED_GUIDE
from .cli import ToolError
from .config import Config
from .resolve import Resolver

CLEAN_GUIDE = "clean.md"


@dataclass
class Rendered:
    text: str
    blocks: bool
    stderr: str = ""


def is_disabled(smell: str, config: Config) -> bool:
    override = config.smells.get(smell)
    return bool(override and override.disabled)


def severity_of(smell: str, config: Config) -> str:
    override = config.smells.get(smell)
    if override and override.severity:
        return override.severity
    return DEFAULT_SEVERITY.get(smell, ENFORCED)


def guide_names(smell: str, config: Config) -> list[str]:
    override = config.smells.get(smell)
    if override and override.guide:
        return [override.guide]
    # Look up ``<smell>.md`` for any smell — catalogued or not — so a custom
    # smell paired with a shipped guide is coached (render_finding falls back to
    # uncoached.md only when no plugin supplies one).
    extensions = ["md", *config.runners.keys()]
    return [f"{smell}.{ext}" for ext in extensions]


def plugins_for_language(language: str | None, config: Config) -> list[str]:
    """``config.plugins`` reordered to coach a finding of ``language``.

    Documented rule: take the first plugin whose declared language matches, in
    ``plugins`` order, then fall back to the languageless plugin (``generic``)
    last. A plugin that declares a *different* language does not coach the
    finding, so its guide is left out.
    """
    languages = config.plugin_languages
    matching = [
        p for p in config.plugins if language is not None and languages.get(p) == language
    ]
    fallback = [p for p in config.plugins if p not in languages]
    return matching + fallback


def include_environment(plugins: list[str], resolver: Resolver) -> Environment:
    def load(name: str) -> str | None:
        partial = resolver.first(plugins, [name])
        return None if partial is None else partial.read_text()

    return Environment(loader=FunctionLoader(load))


def render_markdown(guide: Path, finding: dict, environment: Environment) -> Rendered:
    template = environment.from_string(guide.read_text())
    return Rendered(text=template.render(**finding), blocks=True)


def render_runner(guide: Path, runner: str, finding: dict) -> Rendered:
    result = subprocess.run(
        [runner, str(guide)],
        input=json.dumps(finding),
        capture_output=True,
        text=True,
    )
    return Rendered(
        text=result.stdout,
        blocks=result.returncode != 0,
        stderr=result.stderr,
    )


def _refuse_unconfigured_runner(smell: str, guide: Path, extension: str) -> NoReturn:
    raise ToolError(
        f"habit-mapper: smell {smell!r} routes to guide {guide.name!r}, but the "
        f"{extension!r} extension has no [runners] command — add one or route to "
        f"a .md guide"
    )


def _resolve_guide(finding: dict, config: Config, resolver: Resolver) -> Path:
    plugins = plugins_for_language(finding.get("language"), config)
    guide = resolver.first(plugins, guide_names(finding["smell"], config))
    if guide is None:
        guide = resolver.guide(UNCOACHED_GUIDE, config.plugins)
    return guide


def _runner_for(config: Config, guide: Path, smell: str) -> str:
    """The configured runner command for a non-``.md`` guide, or refuse by name."""
    extension = guide.suffix.lstrip(".")
    runner = config.runners.get(extension)
    if runner is None:
        _refuse_unconfigured_runner(smell, guide, extension)
    return runner


def render_finding(finding: dict, config: Config, resolver: Resolver) -> Rendered:
    smell = finding["smell"]
    enforced = severity_of(smell, config) == ENFORCED
    guide = _resolve_guide(finding, config, resolver)
    if guide.suffix == ".md":
        environment = include_environment(config.plugins, resolver)
        rendered = render_markdown(guide, finding, environment)
    else:
        rendered = render_runner(guide, _runner_for(config, guide, smell), finding)
    rendered.blocks = enforced and rendered.blocks
    return rendered


def render_clean(config: Config, resolver: Resolver) -> Rendered:
    guide = resolver.guide(CLEAN_GUIDE, config.plugins)
    return Rendered(text=guide.read_text(), blocks=False)


def banner(finding: dict) -> str:
    count = len(finding["issues"])
    noun = "issue" if count == 1 else "issues"
    return f"── {finding['smell']} ({count} {noun}) ──"


def block(finding: dict, text: str) -> str:
    """One finding's printed block: its banner, then the guide's text.

    Shared so a run's blocks and a coached incomplete run cannot drift apart.
    """
    return f"{banner(finding)}\n\n{text.strip()}"
