"""Unit tests for a part spelled ``argv``: the form with no shell in it.

A sensor or transformer may spell an argument list instead of shell text, and
that list is spawned as it stands — the only form that runs where there is no
POSIX shell, and where ``bash`` is as likely to be the WSL launcher as a shell.
Nothing is quoted, because nothing reads the arguments as syntax; the
placeholders divide into the two kinds ``command_text`` documents, substituted
inside an element or expanded into arguments of their own.

The shell form is ``tests/test_execution.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from habit_hooks.cli import ConfigError
from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _argv(part: Part, files: list[str]) -> list[str]:
    """The argv spawning ``part`` over ``files`` would carry."""
    execution = Execution(project_dir=part.directory, scope=Scope(files=list(files)))
    return execution._expand(part)


def test_an_argv_part_is_spawned_with_no_shell_around_it(tmp_path: Path) -> None:
    """The whole point of the form: what is written is what is spawned."""
    part = Part(name="probe", directory=tmp_path, argv=["ruff", "check", "--quiet"])

    assert _argv(part, []) == ["ruff", "check", "--quiet"]


def test_no_files_expand_to_no_arguments_at_all(tmp_path: Path) -> None:
    """``${files}`` is a whole element, so an empty scope leaves no empty
    argument behind — a tool handed ``""`` reads it as a path it cannot open."""
    part = Part(name="probe", directory=tmp_path, argv=["ruff", "${files}"])

    assert _argv(part, []) == ["ruff"]


def test_one_file_is_one_argument(tmp_path: Path) -> None:
    part = Part(name="probe", directory=tmp_path, argv=["ruff", "${files}"])

    assert _argv(part, ["src/a.py"]) == ["ruff", "src/a.py"]


def test_many_files_expand_where_the_placeholder_stands(tmp_path: Path) -> None:
    """In place, not appended: a tool's own flags may follow its paths."""
    part = Part(name="probe", directory=tmp_path, argv=["ruff", "${files}", "--json"])

    assert _argv(part, ["src/a.py", "src/b.py"]) == [
        "ruff",
        "src/a.py",
        "src/b.py",
        "--json",
    ]


def test_the_sensor_args_expand_in_place_too(tmp_path: Path) -> None:
    part = Part(
        name="line-count",
        directory=tmp_path,
        argv=["count", "${args}", "${files}"],
        args=["--max", "2 00"],
    )

    assert _argv(part, ["src/a.py"]) == ["count", "--max", "2 00", "src/a.py"]


def test_an_emptied_args_override_expands_to_nothing(tmp_path: Path) -> None:
    """``[sensors.<name>] args = []`` clears a default the project cannot use,
    and an argv with nowhere to put nothing still runs."""
    part = Part(name="line-count", directory=tmp_path, argv=["count", "${args}"])

    assert _argv(part, []) == ["count"]


def test_the_named_config_expands_to_both_of_its_arguments(tmp_path: Path) -> None:
    """``${config}`` carries the whole flag, which is two arguments here — a
    transformer is its own process, so this is how the run's ``--config``
    reaches it."""
    part = Part(name="snooze", directory=tmp_path, argv=["run", "${config}"])
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=[]), config_path=tmp_path / "other.toml"
    )

    assert execution._expand(part) == ["run", "--config", str(tmp_path / "other.toml")]


def test_no_named_config_expands_to_nothing(tmp_path: Path) -> None:
    """Not a dangling ``--config`` with no argument after it."""
    part = Part(name="snooze", directory=tmp_path, argv=["run", "${config}"])

    assert _argv(part, []) == ["run"]


def test_a_string_placeholder_fills_in_inside_its_own_element(tmp_path: Path) -> None:
    """``${dir}`` and ``${python}`` are substituted, not expanded: a bundled
    script's path stays one argument even when the plugin directory — a
    ``site-packages`` path on somebody else's machine — has a space in it."""
    directory = tmp_path / "my plugin"
    part = Part(
        name="line-count", directory=directory, argv=["${python}", "${dir}/count.py"]
    )

    assert _argv(part, []) == [sys.executable, f"{directory}/count.py"]


def test_a_filename_that_is_shell_syntax_reaches_the_tool_intact(
    tmp_path: Path,
) -> None:
    """The argv form's whole safety story, and it is stronger than quoting.

    A scoped path is data that came out of the work tree — from a fork's pull
    request, on a reviewer's machine. The shell form survives it by quoting;
    here there is no shell to read it at all, so the name arrives as the one
    argument it always was, punctuation and all, and nothing in it can run.
    """
    marker = tmp_path / "PWNED"
    name = f"src/it's \"a $(touch {marker}) file\".py"
    (tmp_path / "echo_argv.py").write_text(
        "import sys, json\n"
        'print(json.dumps([{"smell": "s",'
        ' "issues": [{"key": name} for name in sys.argv[1:]]}]))\n',
        encoding="utf-8",
    )
    part = Part(
        name="probe",
        directory=tmp_path,
        argv=["${python}", "${dir}/echo_argv.py", "${files}"],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=[name]))

    findings = execution.run_sensor(part)

    assert findings[0]["issues"] == [{"key": name}]
    assert not marker.exists()


def test_a_list_placeholder_buried_in_a_larger_element_is_refused(
    tmp_path: Path,
) -> None:
    """There is no honest expansion for ``"--paths=${files}"``: the files are
    separate arguments, and joining them into one is the mistake this form
    exists to make impossible. So the author is told, rather than the tool
    being handed one very long filename."""
    part = Part(name="probe", directory=tmp_path, argv=["ruff", "--paths=${files}"])

    with pytest.raises(ConfigError) as refusal:
        _argv(part, ["src/a.py"])

    assert str(refusal.value) == (
        "'probe' cannot expand ${files} inside '--paths=${files}' — it stands "
        "for a whole list of arguments, so it has to be an argv element of its "
        "own; split it into two elements, or use a 'command' string, where a "
        "shell does the splitting"
    )


def test_args_an_argv_has_nowhere_to_put_are_refused_by_name(tmp_path: Path) -> None:
    """The same refusal the shell form earns, asked of the other form: args a
    part cannot expand are args the tool never sees, and #102 refuses a config
    key nothing consumes rather than dropping it."""
    part = Part(
        name="comment", directory=tmp_path, argv=["node", "comment.js"], args=["-v"]
    )

    with pytest.raises(ConfigError) as refusal:
        _argv(part, [])

    assert "cannot take arguments" in str(refusal.value)
