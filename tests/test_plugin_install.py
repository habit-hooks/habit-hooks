"""Unit tests for which command ``habit-hooks init`` offers, and to whom.

A command that cannot work is worse than none: the reader runs it, is told the
same thing again, and has nothing left to try. So the command has to match the
installation habit-hooks is running from. Two are nobody's to install into — a
uv tool environment, which every `uv tool install` rebuilds, and the cache entry
a `uvx` run executes from, which is uv's to prune — and both are answered with
the one command that lasts. A `uv run --with` overlay is nobody's either, but it
names the environment it was layered over, so that one is answered. Anything
else is added to through the interpreter habit-hooks itself runs from, not
whichever ``python`` is on the PATH.

Four of the five have no pip, which is why having none decides nothing here;
what uv wrote in ``pyvenv.cfg`` does.

What the one uv command then names is ``test_uv_tool_command.py``. What init
plans is ``test_initialise.py``; how it says it is ``test_init_report.py``.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest
from habit_hooks.plugin_install import install_commands

PYTHON = shlex.quote(sys.executable)


def test_a_project_missing_no_plugin_is_asked_to_install_nothing(
    pip_installed: None,
) -> None:
    assert install_commands(("python", "generic"), ()) == ()


def test_a_pip_install_goes_through_the_interpreter_habit_hooks_runs_from(
    pip_installed: None,
) -> None:
    """Whichever ``python`` is on the PATH may be another one entirely, and a
    plugin installed there is one this habit-hooks still cannot find."""
    assert install_commands(("python", "generic"), ("python",)) == (
        f"{PYTHON} -m pip install habit-hooks-python",
    )


def test_pip_is_asked_once_per_missing_plugin_in_the_planned_order(
    pip_installed: None,
) -> None:
    """pip adds a package to the environment it is run in, so the commands are
    independent and each names the one plugin it installs."""
    planned = ("python", "typescript", "generic")

    assert install_commands(planned, ("python", "typescript")) == (
        f"{PYTHON} -m pip install habit-hooks-python",
        f"{PYTHON} -m pip install habit-hooks-typescript",
    )


def test_an_interpreter_path_with_a_space_stays_one_word(
    pip_installed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command is offered to a shell, which would otherwise read the path as
    two arguments and run some other python — or none."""
    monkeypatch.setattr(sys, "executable", "/opt/My Tools/bin/python")

    assert install_commands(("python",), ("python",)) == (
        "'/opt/My Tools/bin/python' -m pip install habit-hooks-python",
    )


def test_a_project_venv_is_added_to_rather_than_left_out_of_a_global_install(
    uv_venv: None,
) -> None:
    """A `uv venv` has no pip either, so "no pip" sent a project's own
    environment to `uv tool install` — a *separate*, machine-wide install that
    leaves the venv habit-hooks runs from without the plugin, so the next init
    prints the same line again. That is the loop this module exists to end."""
    assert install_commands(("python", "generic"), ("python",)) == (
        f"uv pip install --python {PYTHON} habit-hooks-python",
    )


def test_a_pip_less_environment_is_asked_once_per_missing_plugin(
    uv_venv: None,
) -> None:
    """`uv pip install` adds to the environment it is pointed at, as pip does,
    so nothing here has to name a plugin it is not installing."""
    planned = ("python", "typescript", "generic")

    assert install_commands(planned, ("python", "typescript")) == (
        f"uv pip install --python {PYTHON} habit-hooks-python",
        f"uv pip install --python {PYTHON} habit-hooks-typescript",
    )


def test_an_overlay_installs_into_the_environment_it_extends(
    uv_run_overlay: str,
) -> None:
    """`uv run --with` runs from a directory under uv's cache that is gone by
    the time anybody reads the command, so naming its interpreter names a Python
    that no longer exists. uv writes down the environment being extended, and
    that one is still there — and is the one the project keeps its plugins in."""
    assert install_commands(("python", "generic"), ("python",)) == (
        f"uv pip install --python {uv_run_overlay} habit-hooks-python",
    )


def test_a_cache_entry_with_a_pip_in_it_is_still_not_one_to_install_into(
    uvx_run_with_a_pip: None,
) -> None:
    """Which question is asked first is the whole rule: a cache entry with a pip
    in it answers ``python -m pip install`` perfectly well, and uv prunes the
    plugin away with the entry."""
    assert install_commands(("python", "generic"), ("python",)) == (
        "uv tool install 'habit-hooks[python]'",
    )


def test_an_environment_that_says_nothing_about_itself_is_taken_for_a_durable_one(
    pip_less_prefix: Path,
) -> None:
    """A Python with neither pip nor a ``pyvenv.cfg`` cannot be shown to be
    throwaway, and the two ways of being wrong are not equal: an install into a
    durable environment that turned out ephemeral is wasted, where a global
    install offered to a durable one is the loop above."""
    assert install_commands(("python", "generic"), ("python",)) == (
        f"uv pip install --python {PYTHON} habit-hooks-python",
    )


def test_a_plugin_name_cannot_say_something_the_config_did_not_in_a_pip_command(
    pip_installed: None,
) -> None:
    """The plugins are named by a config that arrives with a cloned repository,
    and the command built from them is handed to a shell — so a name spelling a
    substitution has to reach that shell as a name."""
    hostile = "$(touch pwned)"

    assert install_commands((hostile,), (hostile,)) == (
        f"{PYTHON} -m pip install 'habit-hooks-$(touch pwned)'",
    )


def test_an_interpreter_with_no_pip_is_never_told_to_run_one(
    uvx_run: None,
) -> None:
    """`uvx` carries no receipt, so it used to fall to the pip branch and answer
    `No module named pip` — the failure this module exists to prevent. A cache
    entry is uv's to reuse and to prune, so a plugin put there is not one this
    machine can be said to hold; what is offered is the install that lasts."""
    assert install_commands(("python", "generic"), ("python",)) == (
        "uv tool install 'habit-hooks[python]'",
    )


def test_a_uv_tool_reinstalls_itself_rather_than_adding_to_itself(
    uv_tool_installed: None,
) -> None:
    """Not because it has no pip — this one has — but because anything pip put
    there would be gone at the next `uv tool install`."""
    assert install_commands(("python", "generic"), ("python",)) == (
        "uv tool install 'habit-hooks[python]'",
    )
