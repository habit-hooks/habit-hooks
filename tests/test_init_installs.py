"""Unit tests for the installs ``habit-hooks init`` offers to run for you.

This is the part with teeth: it runs commands a plugin author wrote, on
somebody's machine. So it has to ask first, ask once, default to no, and never
ask at all where nobody is there to answer — habit-hooks runs inside git hooks
and CI, and a prompt there is not declined, it stops the hook.

Nothing here installs anything real: every command is a shell builtin leaving a
marker behind, so a case can ask what init ran without asking the network.

What init writes is ``test_init_command.py``.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from habit_hooks.init_command import run
from plugin_fixture import write_plugin

RAN = "ran.log"

FIRST = f'{{ name = "wobble-one", kind = "command", install = "echo one >> {RAN}" }}'
SECOND = f'{{ name = "wobble-two", kind = "command", install = "echo two >> {RAN}" }}'
FAILING = '{ name = "wobble-bad", kind = "command", install = "exit 3" }'


class _Terminal(io.StringIO):
    """stdin as a person sitting at one, which ``io.StringIO`` alone is not."""

    def isatty(self) -> bool:
        return True


def _needing(project_dir: Path, *entries: str) -> None:
    """A project whose only plugin declares tools nothing on this machine has,
    each installed by a shell builtin that records that it ran."""
    declared = f"detectors = [{', '.join(entries)}]"
    write_plugin(project_dir, "generic", {"config.toml": declared})


def _answering(answer: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", _Terminal(answer))


def _ran(project_dir: Path) -> list[str]:
    log = project_dir / RAN
    return log.read_text().split() if log.is_file() else []


def test_a_setup_with_nothing_missing_asks_nothing(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(init_project)
    _answering("y\n", monkeypatch)

    assert run([]) == 0
    assert "[y/N]" not in capsys.readouterr().out


def test_nobody_is_prompted_where_nobody_is_there_to_answer(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A git hook and a CI job both run init with stdin closed, where a prompt
    is not declined — it hangs, and the hook with it."""
    _needing(init_project, FIRST)
    monkeypatch.chdir(init_project)

    assert run([]) == 0
    assert "[y/N]" not in capsys.readouterr().out
    assert _ran(init_project) == []


def test_the_commands_are_printed_even_where_they_cannot_be_offered(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A hook that cannot ask still has something worth saying — the reader will
    read it later, in the terminal that ran the hook."""
    _needing(init_project, FIRST)
    monkeypatch.chdir(init_project)

    run([])

    assert f"echo one >> {RAN}" in capsys.readouterr().out


def test_one_prompt_covers_the_whole_list(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A prompt per command is six decisions about nothing where the reader made
    one decision about the setup — and answering the first is then taken as
    consent to a list they have stopped reading."""
    _needing(init_project, FIRST, SECOND)
    monkeypatch.chdir(init_project)
    _answering("y\n", monkeypatch)

    run([])

    assert capsys.readouterr().out.count("[y/N]") == 1


def test_agreeing_runs_every_command_in_the_order_they_were_listed(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _needing(init_project, FIRST, SECOND)
    monkeypatch.chdir(init_project)
    _answering("y\n", monkeypatch)

    assert run([]) == 0
    assert _ran(init_project) == ["one", "two"]


def test_pressing_enter_installs_nothing(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader who pressed it without reading is the one who should not be
    installing anything."""
    _needing(init_project, FIRST)
    monkeypatch.chdir(init_project)
    _answering("\n", monkeypatch)

    assert run([]) == 0
    assert _ran(init_project) == []


def test_declining_installs_nothing(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _needing(init_project, FIRST)
    monkeypatch.chdir(init_project)
    _answering("n\n", monkeypatch)

    run([])

    assert _ran(init_project) == []


def test_a_closed_answer_is_no(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End of input is the reader who walked away, not the reader who agreed."""
    _needing(init_project, FIRST)
    monkeypatch.chdir(init_project)
    _answering("", monkeypatch)

    assert run([]) == 0
    assert _ran(init_project) == []


def test_a_command_that_fails_does_not_take_the_rest_with_it(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One failure is rarely all of them, and stopping at the first hides the
    rest behind a round trip each."""
    _needing(init_project, FAILING, SECOND)
    monkeypatch.chdir(init_project)
    _answering("y\n", monkeypatch)

    run([])

    assert _ran(init_project) == ["two"]


def test_a_command_that_fails_is_named_as_still_to_do(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Buried in the output of the installs that worked, a failure reads as a
    finished setup — and the run that follows fails on the tool."""
    _needing(init_project, FAILING, SECOND)
    monkeypatch.chdir(init_project)
    _answering("y\n", monkeypatch)

    run([])

    reported = capsys.readouterr().out
    assert "These did not succeed, and are still to do:" in reported
    assert reported.rstrip().endswith("  exit 3")
