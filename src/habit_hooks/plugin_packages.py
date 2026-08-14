"""What to ask an index for to get a plugin.

Every answer here is read off installed metadata wherever there is an
installation to read, rather than spelled out, so a plugin added to (or dropped
from) habit-hooks' own packaging cannot leave a stale name behind in a command
someone is about to run. Three questions, one subject:

* which plugins habit-hooks can be asked for **inside its own brackets**;
* which it **brings unasked**, so a command never offers a package it already
  installs;
* what a **single plugin's** distribution is called, which nothing obliges to
  match the plugin's name.

The command built from them is :mod:`habit_hooks.plugin_install`'s, which is
where the environment those names have to suit is settled.
"""

from __future__ import annotations

import re
from importlib.metadata import metadata, requires

from . import resolve

CORE_DISTRIBUTION = "habit-hooks"

# A plugin's distribution, as a requirement of the core names it:
# ``habit-hooks-generic~=1.0`` is the ``generic`` plugin.
PLUGIN_REQUIREMENT = re.compile(rf"{CORE_DISTRIBUTION}-([a-z0-9-]+)")

# What marks a requirement that arrives only when the brackets ask for it —
# ``habit-hooks-python~=1.0; extra == 'python'`` — which is what brackets are for.
EXTRA_MARKER = "extra =="


def provided_extras() -> frozenset[str]:
    """The plugins habit-hooks can be asked for inside its own brackets."""
    return frozenset(metadata(CORE_DISTRIBUTION).get_all("Provides-Extra") or ())


def depended_on_plugins() -> frozenset[str]:
    """The plugins every install of habit-hooks brings whether it says so or not.

    ``habit-hooks`` depends on ``habit-hooks-generic`` outright, so naming it
    with ``--with`` would offer the reader a package the command already
    installs.
    """
    unconditional = (
        line for line in requires(CORE_DISTRIBUTION) or () if EXTRA_MARKER not in line
    )
    named = (PLUGIN_REQUIREMENT.match(line) for line in unconditional)
    return frozenset(match.group(1) for match in named if match)


def distribution(plugin: str) -> str:
    """The package that ships ``plugin``.

    Read off the installation wherever the plugin is installed, because nothing
    obliges a plugin to name its distribution after its entry point and one
    unknown name fails the whole command — including for the plugin that really
    was missing. ``habit-hooks-<name>`` is left as the answer for a plugin
    nobody has yet, where there is nothing to read and the convention is all
    there is to go on.
    """
    installed = resolve.installed_plugin_distributions()
    return installed.get(plugin, f"{CORE_DISTRIBUTION}-{plugin}")
