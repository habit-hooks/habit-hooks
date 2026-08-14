"""Unit tests for every refusal a plugin's ``detectors`` declaration can earn.

A detector is a plugin saying "my sensors reach for this tool, and here is the
command that installs it", so an entry that names a tool without saying how to
get it — or says it in a shape nothing can read — is refused rather than loaded
and half-used. Every refusal quotes the detector it is about, because a config
declares several and one of them being wrong must not send the reader through
all of them.

The refusals a config earns everywhere else are ``test_config_schema.py``; what
an accepted detector contributes to a run is ``test_plugin_defaults.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.config import load_config
from plugin_fixture import write_plugin, write_project_config

COMPLETE = '{ name = "ruff", kind = "command", install = "pip install ruff" }'


def _plugin_declaring(tmp_path: Path, body: str) -> Path:
    """A project running ``alpha``, whose config says whatever ``body`` says."""
    write_project_config(tmp_path, 'plugins = ["alpha"]')
    write_plugin(tmp_path, "alpha", {"config.toml": body})
    return tmp_path


def _detectors(tmp_path: Path, *entries: str) -> Path:
    return _plugin_declaring(tmp_path, f"detectors = [{', '.join(entries)}]")


def _refusal(project_dir: Path) -> str:
    with pytest.raises(SystemExit) as failure:
        load_config(project_dir)
    return str(failure.value)


def test_a_detectors_key_that_is_not_a_list_names_the_plugin_config(
    tmp_path: Path,
) -> None:
    """``detectors = 42`` reached the loader's own ``for`` and escaped as a
    ``TypeError`` at exit 1 — the code reserved for an enforced finding, so CI
    read a mistyped config as a smell in the code (#114)."""
    message = _refusal(_plugin_declaring(tmp_path, "detectors = 42"))

    assert "'detectors'" in message
    assert "the 'alpha' plugin config" in message


def test_a_bare_name_is_refused_as_an_entry_that_is_not_a_table(
    tmp_path: Path,
) -> None:
    """``detectors = ["jq"]`` is the obvious first guess at the syntax. Told it
    is missing three keys, its writer reads an entry that is nearly right; what
    they need told is that an entry is a table."""
    message = _refusal(_detectors(tmp_path, '"jq"'))

    assert "'jq'" in message
    assert "not a table" in message


def test_a_detector_missing_its_install_command_is_refused_by_name(
    tmp_path: Path,
) -> None:
    """The refusal has to survive company: a plugin declaring several detectors
    would otherwise say one of them is incomplete and leave the reader to work
    out which."""
    entry = '{ name = "jq", kind = "command" }'

    message = _refusal(_detectors(tmp_path, COMPLETE, entry))

    assert message == "detector 'jq' is missing key 'install' in the 'alpha' plugin config"


def test_a_detector_with_no_name_is_quoted_whole(tmp_path: Path) -> None:
    """There is nothing to call it by, so the entry itself is what identifies
    it — as a nameless one still has to be findable in a list of them."""
    entry = '{ kind = "command", install = "brew install jq" }'

    message = _refusal(_detectors(tmp_path, COMPLETE, entry))

    assert message == (
        "detector {'kind': 'command', 'install': 'brew install jq'} "
        "is missing key 'name' in the 'alpha' plugin config"
    )


def test_an_unknown_detector_key_is_rejected_by_name(tmp_path: Path) -> None:
    entry = '{ name = "jq", kind = "command", install = "x", when = "always" }'

    assert "'when'" in _refusal(_detectors(tmp_path, entry))


def test_an_unknown_detector_kind_is_rejected_with_the_valid_ones(
    tmp_path: Path,
) -> None:
    """A kind nothing looks for can only be checked by never finding it, so a
    typo would report every project missing a tool it has."""
    entry = '{ name = "jq", kind = "binary", install = "brew install jq" }'

    message = _refusal(_detectors(tmp_path, entry))

    assert "'binary'" in message
    assert "the 'alpha' plugin config" in message
    assert "'command', 'node-module'" in message


def test_an_install_command_written_as_a_list_is_refused(tmp_path: Path) -> None:
    """A list is the natural wrong guess — ``args = [...]`` is how this repo
    spells a command elsewhere — and it is not a command anything can offer to
    run for you."""
    entry = '{ name = "jq", kind = "command", install = ["brew", "install", "jq"] }'

    message = _refusal(_detectors(tmp_path, entry))

    assert "detector 'jq'" in message
    assert "'install'" in message
    assert "non-empty string" in message


def test_a_name_that_is_not_a_string_is_refused(tmp_path: Path) -> None:
    """Nothing can be looked for under a name no shell could spell."""
    entry = '{ name = 1, kind = "command", install = "brew install jq" }'

    message = _refusal(_detectors(tmp_path, entry))

    assert "'name'" in message
    assert "non-empty string" in message


def test_an_empty_install_command_is_refused_like_a_missing_one(
    tmp_path: Path,
) -> None:
    """A detector missing its install names a tool and then leaves the reader to
    find it. An empty string does exactly that, while looking complete."""
    entry = '{ name = "jq", kind = "command", install = "" }'

    message = _refusal(_detectors(tmp_path, entry))

    assert "detector 'jq'" in message
    assert "'install'" in message
    assert "non-empty string" in message


def test_a_project_may_not_declare_detectors(tmp_path: Path) -> None:
    """Detectors are a plugin's statement of what its sensors reach for; a
    project naming one would be declaring a need nothing it runs has."""
    write_project_config(tmp_path, 'detectors = [{ name = "jq", kind = "command" }]')

    message = _refusal(tmp_path)

    assert "'detectors'" in message
    assert "the project config" in message
