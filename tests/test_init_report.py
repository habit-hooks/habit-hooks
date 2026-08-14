"""Unit tests for what ``habit-hooks init`` says about a plan.

Every case here is somebody's first ten minutes with the tool, so the lines are
asserted for what they let the reader do next: install a plugin, install a tool,
run habit-hooks, or write a plugin of their own. A report with nothing to do at
the end of it is the loop init exists to break.

What init decides is ``test_initialise.py``; what it then runs is
``test_init_command.py``.
"""

from __future__ import annotations

from habit_hooks.detectors import Detector
from habit_hooks.init_report import AUTHORING_GUIDE, LANGUAGE, report
from habit_hooks.initialise import Plan

JQ = Detector(name="jq", kind="command", install="brew install jq")
NODE = Detector(name="node", kind="command", install="brew install node")


def _plan(**overrides) -> Plan:
    """A plan for a configured python project with nothing in its way."""
    return Plan(
        **{
            "languages": ("python",),
            "plugins": ("python", "generic"),
            "already_configured": True,
            "missing_tools": (),
            "uninstalled_plugins": (),
            "plugin_installs": (),
            **overrides,
        }
    )


def _reported(**overrides) -> str:
    return "\n".join(report(_plan(**overrides)))


def test_a_fresh_project_is_told_the_config_was_written_and_what_it_enables() -> None:
    reported = _reported(already_configured=False)

    assert "Wrote .habit-hooks/config.toml, enabling python, generic." in reported


def test_a_configured_project_is_told_its_config_was_left_alone() -> None:
    """The doctor case: it answers "why is this run reporting nothing?" and must
    not become the thing that changed the answer."""
    reported = _reported()

    assert "Left as it is." in reported
    assert "Wrote" not in reported


def test_a_configured_project_is_told_which_plugins_its_config_enables() -> None:
    assert "enables python, generic." in _reported()


def test_a_config_that_enables_nothing_says_so_rather_than_trailing_off() -> None:
    """Every plugin switched off is the commonest reason a run reports nothing,
    so the line has to be readable as an answer rather than as a blank."""
    assert "enables no plugins." in _reported(plugins=())


def test_a_detected_language_is_named_whether_or_not_the_config_covers_it() -> None:
    assert _reported().startswith("Detected: python.")


def test_a_setup_with_nothing_in_its_way_says_so_and_points_at_a_run() -> None:
    assert "Nothing missing — run `habit-hooks` to see what it finds." in _reported()


def test_one_missing_tool_is_named_beside_the_command_that_installs_it() -> None:
    """Naming the tool alone leaves the reader to go and find it, which is the
    whole of what init is for."""
    reported = _reported(missing_tools=(JQ,))

    assert "  jq   brew install jq" in reported
    assert "Nothing missing" not in reported


def test_every_missing_tool_is_named_in_the_order_its_plugin_declared_them() -> None:
    """A plugin declares what everything else needs first, so a list read from
    the top is one that can be worked through from the top."""
    reported = _reported(missing_tools=(NODE, JQ)).splitlines()

    assert [line for line in reported if "brew" in line] == [
        "  node   brew install node",
        "  jq     brew install jq",
    ]


def test_an_uninstalled_plugin_is_reported_before_any_missing_tool() -> None:
    """Nothing runs without the plugin, and the tools it declares cannot even be
    looked for until it is there — so it is the first thing to do."""
    reported = _reported(
        missing_tools=(JQ,),
        uninstalled_plugins=("python",),
        plugin_installs=("pip install habit-hooks-python",),
    ).splitlines()

    assert reported.index("  pip install habit-hooks-python") < reported.index(
        "  jq   brew install jq"
    )


def test_the_plugins_nobody_has_are_named_with_the_command_that_gets_them() -> None:
    reported = _reported(
        uninstalled_plugins=("python", "typescript"),
        plugin_installs=("uv tool install 'habit-hooks[python,typescript]'",),
    )

    assert "nothing runs without them: python, typescript" in reported
    assert "  uv tool install 'habit-hooks[python,typescript]'" in reported


def test_a_missing_plugin_sends_the_reader_back_through_init() -> None:
    """A newly installed plugin declares tools of its own that were invisible
    until now, so pointing at a run here would call the setup finished a round
    early — and the run would then fail on those tools."""
    reported = _reported(
        uninstalled_plugins=("python",),
        plugin_installs=("pip install habit-hooks-python",),
    )

    assert "run `habit-hooks init` again" in reported


def test_a_missing_tool_alone_points_straight_at_a_run() -> None:
    """Nothing new can appear from installing a tool, so there is no second
    round to send anybody through."""
    reported = _reported(missing_tools=(JQ,))

    assert "Install these, then run `habit-hooks`." in reported


def test_an_unrecognised_project_is_offered_a_plugin_to_write() -> None:
    """There is nothing to install for a language habit-hooks never heard of, so
    the offer is a different one — and the useful thing to hand someone is the
    prompt that gets the plugin written."""
    reported = _reported(languages=(), plugins=("generic",))

    assert "Detected: no language habit-hooks has a plugin for." in reported
    assert "habit-hooks ships plugins for python, typescript and php." in reported


def test_the_prompt_sends_the_agent_to_the_authoring_manual() -> None:
    """An agent that starts writing without it invents a plugin layout the
    resolver will never find."""
    reported = _reported(languages=(), plugins=("generic",))

    assert AUTHORING_GUIDE in reported
    assert "docs/authoring-plugins.spec.md" in AUTHORING_GUIDE


def test_the_prompt_leaves_the_language_to_the_reader() -> None:
    """Nothing was recognised, so any language named here would be the tool
    inventing one for the reader to correct."""
    reported = _reported(languages=(), plugins=("generic",))

    assert f"Write a habit-hooks plugin for {LANGUAGE}." in reported


def test_a_recognised_project_is_not_offered_a_plugin_to_write() -> None:
    assert "hand this to your coding agent" not in _reported()


def test_the_offer_of_a_plugin_to_write_never_ends_the_report() -> None:
    """The prompt is a wall of text meant for an agent, and a reader left
    looking at it is a reader whose own next step scrolled past."""
    reported = _reported(languages=(), plugins=("generic",), missing_tools=(JQ,))

    assert reported.rstrip().endswith("Install these, then run `habit-hooks`.")
