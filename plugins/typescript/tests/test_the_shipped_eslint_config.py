"""The config the plugin ships: what it reports, and whether it loads at all.

The plugin never ran its own flat config, so nothing lined the two up. It paired
base ``no-unused-vars`` with ``@typescript-eslint/no-unused-vars`` the wrong way
round: the base rule cannot see type positions, so an interface's method
parameter names — documentation, and not removable without breaking the
TypeScript — came back as unused variables at error severity (#113).

Every case runs the real eslint from the plugin's own ``node_modules``: a rule
pairing is only true of the tool that reads it. What the sensor's smell map then
makes of the rule IDs is ``test_the_eslint_smell_map.py``; whether this config is
the one that runs at all is ``test_which_eslint_config_wins.py``.
"""

from __future__ import annotations

from pathlib import Path

from eslint_project import SHIPPED_CONFIG, UNUSED_LOCAL_LINE, messages, project


def test_an_interface_method_parameter_is_not_an_unused_variable(
    tmp_path: Path,
) -> None:
    """`item` and `id` name what the implementer must pass; only `unusedTax` is
    dead."""
    reported = messages(project(tmp_path), SHIPPED_CONFIG)

    assert [message["line"] for message in reported] == [UNUSED_LOCAL_LINE], reported


def test_the_unused_local_is_reported_by_the_typescript_rule(tmp_path: Path) -> None:
    """The pairing decides which rule ID the finding will carry downstream."""
    reported = messages(project(tmp_path), SHIPPED_CONFIG)

    assert [message["ruleId"] for message in reported] == [
        "@typescript-eslint/no-unused-vars"
    ]


def test_the_config_loads_from_where_it_ships(tmp_path: Path) -> None:
    """Once the sensor names the shipped config, that file is read from wherever
    habit-hooks is installed — for a consumer, a Python ``site-packages`` tree
    with no ``node_modules`` anywhere above it. A bare ``import`` in the config
    resolves against *that* directory and dies with ``ERR_MODULE_NOT_FOUND``, so
    the parser and plugin have to come from the project, which is where eslint
    itself came from.
    """
    consumer = project(tmp_path)
    installed = tmp_path / "site-packages" / "habit_hooks_typescript"
    installed.mkdir(parents=True)
    shipped = installed / SHIPPED_CONFIG.name
    shipped.write_bytes(SHIPPED_CONFIG.read_bytes())

    reported = messages(consumer, shipped)

    assert [message["line"] for message in reported] == [UNUSED_LOCAL_LINE], reported
