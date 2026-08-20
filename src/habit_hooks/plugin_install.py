"""What installs a plugin into *this* habit-hooks.

Naming a command that cannot work recreates the very bug ``habit-hooks init``
exists to end: a reader runs what they were told, is met by the same line again,
and nothing in it can change the outcome. So the command answers to what this
environment can be *added to*, and five answers are all ordinary:

* a **uv run --with** overlay, known by the ``extends-environment`` line naming
  what it was layered over, is a directory under uv's cache that is gone by the
  time anybody reads the command — so the environment to name is the durable
  one it extends, which uv has written down for us.
* a **uv tool** environment, known by its receipt, is *replaced* wholesale by
  every ``uv tool install``, so one command per missing plugin would leave only
  the last of them installed — hence one command naming them together, and
  naming every **planned** plugin a package supplies rather than only the
  missing ones, so the command that adds one cannot delete another the project
  already has.
* a **uvx** run, known by the ``relocatable`` line, executes from an entry in
  uv's own cache: keyed on the request, reused by the next identical run and
  pruned whenever uv decides — nobody's to install into, so what it is offered
  is the ``uv tool install`` that lasts.
* an environment with **pip** — a pip install, a ``python -m venv``, the
  Homebrew Cellar venv — installs through the **running interpreter**, which is
  what stops a plugin landing in some other Python than the one habit-hooks
  runs from.
* everything else is a **durable environment without pip**, which is what every
  ``uv venv`` is — including the one a project habit-hooks is a dev dependency
  of runs it from. It is added to with ``uv pip install --python``. Offering
  *that* project a ``uv tool install`` is offering it a second, machine-wide
  habit-hooks that leaves its own environment exactly as it was, so the next
  init says the same thing again.

The last two are why having no pip cannot be the question: a ``uv venv`` has no
more pip than a ``uvx`` cache entry has. What uv wrote in ``pyvenv.cfg`` is, and
the order the two lines are read in is the rule — an overlay's own interpreter
is as ephemeral as a cache entry's, but unlike one it names an environment that
is not.

Which of the five this is answers to :mod:`habit_hooks.initialise`, never to a
printed line: the command is a decision like any other the plan makes. What the
packages it names are called is :mod:`habit_hooks.plugin_packages`.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Sequence
from importlib.util import find_spec
from pathlib import Path

from .plugin_packages import (
    CORE_DISTRIBUTION,
    depended_on_plugins,
    distribution,
    provided_extras,
)

# uv writes this beside ``pyvenv.cfg`` in a tool environment and in no other kind
# of venv, so it is what tells a ``uv tool install`` apart from a ``uv venv`` —
# which is equally without pip, and where a `uv tool install` would install
# beside the project rather than into it.
UV_TOOL_RECEIPT = "uv-receipt.toml"

# Where a virtual environment records how it was made, and the two settings uv
# writes there about environments it owns rather than a person does.
VENV_CONFIG = "pyvenv.cfg"
RELOCATABLE = "relocatable"
EXTENDED_ENVIRONMENT = "extends-environment"


def _installed_as_a_uv_tool() -> bool:
    return (Path(sys.prefix) / UV_TOOL_RECEIPT).is_file()


def _uv_tool_command(packaged: Sequence[str]) -> str:
    """The one command that leaves this tool holding every plugin in ``packaged``.

    ``uv tool install`` rebuilds the environment rather than adding to it, so
    what the command leaves out is what it *deletes*: every planned plugin has
    to be named, not only the missing ones. habit-hooks spells its own in the
    brackets and brings the ones it depends on unasked; anything else — a plugin
    somebody wrote themselves — is named with ``--with``, in this same command,
    because a second ``uv tool install`` would replace everything the first one
    just put there.

    Every name goes through ``shlex.quote``: the plugins are a config's to name,
    a config is a cloned repository's to write, and this string is handed to a
    shell. Brackets need quoting from that shell in any case, and quoting them
    this way leaves nothing for the plugin name inside them to escape.
    """
    extras = provided_extras()
    shipped = ",".join(plugin for plugin in packaged if plugin in extras)
    target = f"{CORE_DISTRIBUTION}[{shipped}]" if shipped else CORE_DISTRIBUTION
    brought_by_habit_hooks = extras | depended_on_plugins()
    separate = "".join(
        f" --with {shlex.quote(distribution(plugin))}"
        for plugin in packaged
        if plugin not in brought_by_habit_hooks
    )
    return f"uv tool install {shlex.quote(target)}{separate}"


def _venv_settings() -> dict[str, str]:
    """What ``sys.prefix``'s ``pyvenv.cfg`` says about itself, if anything.

    Unreadable is treated as unsaid rather than raised: ``init`` is the command
    someone runs in their first ten minutes, and a stack trace out of a file
    they have never heard of tells them nothing they can act on.
    """
    config = Path(sys.prefix) / VENV_CONFIG
    try:
        lines = config.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    settings = (line.partition("=") for line in lines)
    return {key.strip(): value.strip() for key, _, value in settings}


def _a_cache_entry_uv_owns() -> bool:
    """Whether this environment is uv's to keep or prune, rather than anyone's
    to install into.

    Measured, not assumed (uv 0.8.11): uv writes ``relocatable = true`` into the
    ``pyvenv.cfg`` of the cache entry a ``uvx`` run executes from, and into no
    environment it hands to a person — a ``uv tool install`` has no such line,
    and nor has a plain ``uv venv``. Such an entry is reused by the next
    identical ``uvx``, so it is not thrown away at the end of the run; it is
    keyed on the request and pruned at uv's discretion, which is why a plugin
    installed into one cannot be relied on to be there. Having no pip says
    nothing here: none of these environments has one.

    The one environment this reads wrongly is ``uv venv --relocatable``, which
    carries the line and is a person's. Locating uv's cache instead would tell
    the two apart exactly, but only by reimplementing uv's own answer to where
    its cache is (``UV_CACHE_DIR``, then a per-platform default) — a guess that
    fails silently and, unlike this one, in the direction of offering a durable
    environment a global install.
    """
    return _venv_settings().get(RELOCATABLE) == "true"


def _pip_can_be_run() -> bool:
    """Whether ``python -m pip`` is a command this interpreter would answer."""
    return find_spec("pip") is not None


def _uv_pip_command(environment: str, plugin: str) -> str:
    """``uv pip``, which is how uv adds to an environment that has no pip.

    Quoted, because a Python installed under a path with a space in it is
    otherwise two words to the shell that runs this. Reaching for uv rests on
    an environment uv made being on a machine that has uv; a
    ``python -m venv --without-pip`` would be told to run a uv it may not have,
    which at least says so out loud rather than answering ``No module named
    pip``.
    """
    return (
        f"uv pip install --python {shlex.quote(environment)} "
        f"{shlex.quote(distribution(plugin))}"
    )


def _added_to_this_environment(plugin: str) -> str:
    """The command that puts one plugin beside the habit-hooks already here.

    Spelled with the running interpreter either way, which is what stops a
    plugin landing in some other Python than the one habit-hooks runs from.
    """
    if _pip_can_be_run():
        return (
            f"{shlex.quote(sys.executable)} -m pip install "
            f"{shlex.quote(distribution(plugin))}"
        )
    return _uv_pip_command(sys.executable, plugin)


def install_commands(
    packaged: Sequence[str], uninstalled: Sequence[str]
) -> tuple[str, ...]:
    """The commands that put ``uninstalled`` within this habit-hooks' reach.

    ``packaged`` is every plugin this environment has to end up holding as a
    package, which a uv tool needs and pip does not: pip adds a package to an
    environment, where uv rebuilds one. A plugin on hand only by being vendored
    under ``.habit-hooks/`` is not one of them — it is not a package at all, and
    naming it would fail the whole install on a name PyPI never heard of.
    """
    if not uninstalled:
        return ()
    extended = _venv_settings().get(EXTENDED_ENVIRONMENT)
    if extended is not None:
        return tuple(_uv_pip_command(extended, plugin) for plugin in uninstalled)
    if _installed_as_a_uv_tool() or _a_cache_entry_uv_owns():
        return (_uv_tool_command(packaged),)
    return tuple(_added_to_this_environment(plugin) for plugin in uninstalled)
