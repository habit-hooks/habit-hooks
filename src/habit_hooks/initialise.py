"""What setting a project up decides, before a word of it is printed.

Installing habit-hooks is its most frequent support question, and the answer is
always the same three things: which plugins this project wants, whether it is
already configured, and which of the tools those plugins reach for this machine
has not got. They are settled here as data, so the command that reports them —
and offers to run an install — has nothing left to decide.

Two of the three are deliberately asked exactly as a run asks them, because a
project told one thing at setup and shown another on its first run is worse off
than one that was never set up: a language is detected through ``recommend``'s
own signals, and a tool is looked for where a run would spawn it. That half is
:mod:`habit_hooks.missing_tools`, kept apart from the planning because it is the
only part of setting a project up that spawns anything.

Re-run on a project that already has a config, the plan changes nothing and
reports on the plugins that config names — so the same command doubles as the
answer to "why is this run not reporting anything?".
"""

from __future__ import annotations

from pathlib import Path

from attrs import frozen

from . import git_history
from .config import declared_detectors, load_config, project_config_path
from .config_schema import Config
from .detectors import Detector
from .missing_tools import missing_tools
from .recommend import used_languages

# The plugin every project gets: it speaks no language, so nothing it reports
# depends on what the project is written in.
LANGUAGE_AGNOSTIC_PLUGIN = "generic"


@frozen
class Plan:
    """What setting this project up comes to, and what stands in the way.

    ``plugins`` is what the project will run: a plugin per language it uses,
    then the languageless ``generic`` — or, where it is already configured, the
    plugins its own config names, because a re-run reports on the run the
    project actually gets. ``languages`` is what was detected either way, so a
    language its config leaves uncovered is still visible.
    """

    languages: tuple[str, ...]
    plugins: tuple[str, ...]
    already_configured: bool
    missing_tools: tuple[Detector, ...]

    @property
    def needs_a_new_plugin(self) -> bool:
        """Whether this is a project habit-hooks has no plugin for at all.

        Nothing was recognised, so what is on offer is not a plugin to install
        but one to write — a different thing to say, and the CLI's to say.
        """
        return not self.languages


def plan(project_dir: Path) -> Plan:
    """Everything setting this project up needs decided, and nothing acted on."""
    files = git_history.project_files(project_dir)
    languages = tuple(used_languages(project_dir, files))
    config = _project_config(project_dir)
    plugins = _plugins(languages, config)
    declared = _declared_tools(plugins, project_dir, config)
    missing = missing_tools(declared, project_dir)
    return Plan(languages, plugins, config is not None, missing)


def _project_config(project_dir: Path) -> Config | None:
    """The project's own config, loaded once, or ``None`` where it has none.

    Loaded rather than merely found, because a configured project's plugins and
    everything those plugins declare both come out of the one load — asking for
    either separately reads and re-refuses every plugin config a second time.
    """
    if not project_config_path(project_dir).is_file():
        return None
    return load_config(project_dir)


def _plugins(languages: tuple[str, ...], config: Config | None) -> tuple[str, ...]:
    """The plugins this project runs: the ones it names, or the ones it needs.

    A plugin is named for the language it speaks, so the languages *are* the
    plugins; ``generic`` goes behind them because ``plugins`` order is the
    priority the mapper reads, and the languageless fallback comes last.
    """
    if config is not None:
        return tuple(config.plugins)
    return (*languages, LANGUAGE_AGNOSTIC_PLUGIN)


def _declared_tools(
    plugins: tuple[str, ...], project_dir: Path, config: Config | None
) -> list[Detector]:
    """What these plugins need installed — the config's own answer where it has
    one, and asked of the plugins this project is about to switch on where it
    has not."""
    if config is not None:
        return config.plugin_detectors
    return declared_detectors(list(plugins), project_dir)
