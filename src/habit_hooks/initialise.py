"""What setting a project up decides, before a word of it is printed.

Installing habit-hooks is its most frequent support question, and the answer is
always the same few things: which plugins this project wants, whether it is
already configured, which of those plugins are nowhere to be found, and which of
the tools they reach for this machine has not got. They are settled here as
data, so the command that reports them — and offers to run an install — has
nothing left to decide.

Every one of them is deliberately asked exactly as a run asks it, because a
project told one thing at setup and shown another on its first run is worse off
than one that was never set up: a language is detected through ``recommend``'s
own signals, a plugin is looked for through the resolver, and a tool is looked
for where a run would spawn it. Two of those live apart — the looking is
:mod:`habit_hooks.missing_tools`, the only part of setting a project up that
spawns anything, and what installs a missing plugin into *this* habit-hooks is
:mod:`habit_hooks.plugin_install`.

Re-run on a project that already has a config, the plan changes nothing and
reports on the plugins that config names — so the same command doubles as the
answer to "why is this run not reporting anything?".
"""

from __future__ import annotations

from pathlib import Path

from attrs import frozen

from . import git_listing
from .config import declared_detectors, load_config, project_config_path
from .config_schema import Config
from .detectors import Detector
from .missing_tools import missing_tools
from .plugin_install import install_commands
from .recommend import used_languages
from .resolve import Resolver

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

    ``uninstalled_plugins`` is the half a run cannot survive: a plugin nobody
    has stops the first run dead on ``Resolver.require_plugin``, where a missing
    tool costs only that sensor's findings. ``plugin_installs`` is what fixes
    it, spelled for the way this habit-hooks was installed.
    """

    languages: tuple[str, ...]
    plugins: tuple[str, ...]
    already_configured: bool
    missing_tools: tuple[Detector, ...]
    uninstalled_plugins: tuple[str, ...]
    plugin_installs: tuple[str, ...]

    @property
    def needs_a_new_plugin(self) -> bool:
        """Whether this is a project habit-hooks has no plugin for at all.

        Nothing was recognised *and* nothing is planned but the languageless
        plugin, so what is on offer is not a plugin to install but one to write
        — a different thing to say, and the CLI's to say. A project running a
        plugin of its own has already taken that advice, and being handed it
        again every run is the loop a hint that names what its reader has done
        becomes.
        """
        beyond_the_languageless = set(self.plugins) - {LANGUAGE_AGNOSTIC_PLUGIN}
        return not self.languages and not beyond_the_languageless

    @property
    def installs(self) -> tuple[str, ...]:
        """Every command this setup asks for, in the order they are worth running.

        Plugins first because nothing runs without them, and because a plugin
        declares tools of its own that cannot be looked for until it is there;
        then the tools, in the order their plugins declared them, which is the
        order a list can be worked through from the top.
        """
        return (
            *self.plugin_installs,
            *(detector.install for detector in self.missing_tools),
        )


def plan(project_dir: Path) -> Plan:
    """Everything setting this project up needs decided, and nothing acted on."""
    files = git_listing.project_files(project_dir)
    languages = tuple(used_languages(project_dir, files))
    config = _project_config(project_dir)
    plugins = _plugins(languages, config)
    declared = _declared_tools(plugins, project_dir, config)
    missing = missing_tools(declared, project_dir)
    resolver = Resolver.discover(project_dir)
    uninstalled = _uninstalled_plugins(plugins, resolver)
    return Plan(
        languages,
        plugins,
        config is not None,
        missing,
        uninstalled,
        install_commands(_packaged_plugins(plugins, resolver), uninstalled),
    )


def _uninstalled_plugins(
    plugins: tuple[str, ...], resolver: Resolver
) -> tuple[str, ...]:
    """The planned plugins this project has no files for, in ``plugins`` order.

    Asked as ``Resolver.has_plugin``, the question a run itself asks, so "you
    configured a plugin that is not there" and "you have one you never switched
    on" can never disagree about what counts as having one — a plugin vendored
    under ``.habit-hooks/<name>/`` is on hand exactly as an installed package is.
    Without this a setup planning a plugin nobody has reports nothing missing,
    and the first run then dies on ``require_plugin``: the situation this whole
    command exists to spare someone working out for themselves.
    """
    return tuple(plugin for plugin in plugins if not resolver.has_plugin(plugin))


def _packaged_plugins(
    plugins: tuple[str, ...], resolver: Resolver
) -> tuple[str, ...]:
    """Every plugin an install has to leave this habit-hooks holding.

    Everything installed as a package, and then the planned plugins nobody has
    yet. Installed comes first and in full because ``uv tool install`` rebuilds
    the environment rather than adding to it — so it deletes every plugin the
    command leaves out — and that environment serves the whole machine: name
    only the plugins this project plans and the command uninstalls the ones the
    project next door runs. A plugin vendored under ``.habit-hooks/<name>/`` is
    in neither half: it is files in the project, usually on no index at all, and
    naming it would fail the whole install rather than preserve anything.
    """
    installed = tuple(resolver.package_dirs)
    return (*installed, *(p for p in plugins if not resolver.has_plugin(p)))


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
