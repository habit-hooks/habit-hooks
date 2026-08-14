"""What ``habit-hooks init`` says about a plan, and nothing about when.

Kept apart from :mod:`habit_hooks.initialise` for the reason
:mod:`habit_hooks.rendering` is kept apart from ``mapper``: every question
setting a project up asks must be answerable without printing a word, so the
decisions stay testable as data and the wording stays free to change. The
dependency runs one way (report → plan) and must stay that way.

The order is the order the reader can act in. Plugins before tools, because
nothing runs without a plugin and because a plugin declares tools of its own
that cannot even be looked for until it is there — which is also why anything
missing ends by pointing back at ``habit-hooks init`` rather than at a run.
"""

from __future__ import annotations

from .initialise import Plan

AUTHORING_GUIDE = (
    "https://github.com/habit-hooks/habit-hooks"
    "/blob/main/docs/authoring-plugins.spec.md"
)

SHIPPED_LANGUAGES = "python, typescript and php"

# Left as a placeholder rather than guessed: nothing was recognised, so any
# language named here would be this tool inventing one for the reader to correct.
LANGUAGE = "<your language>"

AGENT_PROMPT = (
    f"Write a habit-hooks plugin for {LANGUAGE}. Read",
    f"  {AUTHORING_GUIDE}",
    "first — it is the end-to-end manual and it runs top to bottom. Follow it",
    f"to build an installable habit-hooks-{LANGUAGE} package with a sensor that",
    f"finds one real structural smell in {LANGUAGE} and a guide that coaches",
    "the fix, then install it and enable it in .habit-hooks/config.toml.",
)


def _detected(planned: Plan) -> str:
    if not planned.languages:
        return "Detected: no language habit-hooks has a plugin for."
    return f"Detected: {', '.join(planned.languages)}."


def _listed(plugins: tuple[str, ...]) -> str:
    return ", ".join(plugins) or "no plugins"


def _configuration(planned: Plan) -> str:
    """The one line about the config file, which a re-run must not have touched."""
    if planned.already_configured:
        return (
            f"Already configured: .habit-hooks/config.toml enables "
            f"{_listed(planned.plugins)}. Left as it is."
        )
    return f"Wrote .habit-hooks/config.toml, enabling {_listed(planned.plugins)}."


def _plugins_block(planned: Plan) -> list[str]:
    """The missing plugins, then the command that installs them.

    Named together rather than each beside its own command: under a uv tool
    install one command covers all of them, and printing it once per plugin
    would read as several installs where running two of them undoes the first.
    """
    if not planned.uninstalled_plugins:
        return []
    return [
        "",
        "Plugins not installed — nothing runs without them: "
        + ", ".join(planned.uninstalled_plugins),
        *(f"  {command}" for command in planned.plugin_installs),
    ]


def _tools_block(planned: Plan) -> list[str]:
    """Every missing tool beside the command that installs it, in the order its
    plugin declared them — which puts what everything else needs at the top."""
    if not planned.missing_tools:
        return []
    width = max(len(detector.name) for detector in planned.missing_tools)
    return [
        "",
        "Tools this machine has not got:",
        *(
            f"  {detector.name.ljust(width)}   {detector.install}"
            for detector in planned.missing_tools
        ),
    ]


def _closing(planned: Plan) -> list[str]:
    """Where to go next, which is never nowhere and always last on screen.

    A missing plugin sends the reader back through init, because the plugin's
    own tools are invisible until it is installed and a setup that stopped here
    would call itself finished one round early.
    """
    if not planned.installs:
        return ["", "Nothing missing — run `habit-hooks` to see what it finds."]
    if planned.uninstalled_plugins:
        return [
            "",
            "Install these, then run `habit-hooks init` again: a plugin declares",
            "tools of its own, which cannot be looked for until it is installed.",
        ]
    return ["", "Install these, then run `habit-hooks`."]


def _new_plugin_block(planned: Plan) -> list[str]:
    """What to do about a language habit-hooks has never heard of.

    There is nothing to install here, so the offer is a plugin to *write*, and
    the useful thing to hand someone is the prompt that gets one written.
    """
    if not planned.needs_a_new_plugin:
        return []
    return [
        "",
        f"habit-hooks ships plugins for {SHIPPED_LANGUAGES}. For anything else the",
        f"plugin is one to write — hand this to your coding agent, with {LANGUAGE}",
        "filled in:",
        "",
        *(f"  {line}" for line in AGENT_PROMPT),
    ]


def report(planned: Plan) -> list[str]:
    """Everything ``habit-hooks init`` has to say about ``planned``, in order."""
    return [
        _detected(planned),
        _configuration(planned),
        *_plugins_block(planned),
        *_tools_block(planned),
        *_new_plugin_block(planned),
        *_closing(planned),
    ]
