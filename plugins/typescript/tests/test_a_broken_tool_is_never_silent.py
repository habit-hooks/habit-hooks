"""A tool that failed always gets a sentence saying so — and only a sentence.

An empty complaint is #142. ``spawnSync`` answers a stdout over its buffer with
ENOBUFS, a ``null`` status and a *blank* stderr; the eslint sensor forwarded the
blank, so the whole notice a reader got was the sensor's own command line —
told that a sensor failed, and never what failed about it.

So the seam both Node sensors run their tool through
(``sensors/project_tool.cjs``) owns two questions neither caller may answer for
itself: whether the run broke, and what to say about it. The words are the
tool's own wherever the tool has any, because a tool that diagnosed itself is
the thing a reader can act on; where it has none the seam speaks for it, and
then it must say WHICH tool — ``spawnSync <path to node> ENOBUFS`` names the
runtime, which is never the tool that failed.

The other half is that a complaint stays *short*. What a tool half-printed to
stdout is a cut-off report, not a diagnosis, and a sensor's whole stderr goes
into a reading agent's context: ``sensors/diagnosis.py`` trims a long one by
LINES, which does nothing at all to the single line ``eslint -f json`` emits.

``project_tool_probe`` is how the seam is asked; what it is asked about is
here. That its two callers really ask is
``test_both_node_sensors_refuse_alike.py``.
"""

from __future__ import annotations

from pathlib import Path

from project_tool_probe import a_project_whose_tool, ask_the_seam, judge

SAYS_NOTHING = "process.exit(2);\n"
COMPLAINS = 'process.stderr.write("knip.json: line 3 is nonsense\\n");\nprocess.exit(2);\n'

# Comfortably past a pipe's own 64KB buffer, so the report really is in flight
# rather than sitting in the tool. Nothing here needs the megabytes the OOM
# killer would really have let through: what matters is that the complaint does
# not grow with it.
PARTIAL_REPORT_BYTES = 100_000

# A tool the OOM killer reached on a big repository, after it had flushed most
# of a report: a large half-written stdout, a stderr holding nothing but
# whitespace, and no exit code at all. `fs.writeSync` rather than
# `process.stdout.write` so the bytes are really in the pipe before the signal
# lands — a write still queued in the tool would make this case pass for the
# wrong reason.
KILLED_MID_REPORT = (
    'const fs = require("node:fs");\n'
    f'fs.writeSync(1, "[".padEnd({PARTIAL_REPORT_BYTES}, "x"));\n'
    'fs.writeSync(2, "  \\n");\n'
    'process.kill(process.pid, "SIGKILL");\n'
)

# A run `spawnSync` could not complete: no exit code, an error naming the node
# it spawned rather than the tool, and whatever the tool got out before it went.
A_SPAWN_THAT_DIED = {
    "status": None,
    "signal": "SIGTERM",
    "error": {"message": "spawnSync /usr/local/bin/node ENOBUFS"},
    "stdout": '[{"filePath":"/p/src/a.ts","mess',
    "stderr": "",
}

# A spawn that never started at all. `spawnSync` answers with no streams to
# speak of — absent, not empty — and it is reachable through `run` as E2BIG:
# the core budgets the *sensor's* argv, and the helper then spawns one process
# further in with the tool's own script path added
# (`part_output.py` already concedes the budget can guess wrong). Node 22
# answers ENOENT the same way.
A_SPAWN_THAT_NEVER_STARTED = {
    "status": None,
    "signal": None,
    "error": {"message": "spawnSync /usr/local/bin/node E2BIG"},
    "stdout": None,
    "stderr": None,
}

# The same, by a tool that got its own diagnosis out first.
A_SPAWN_THAT_DIED_AFTER_SPEAKING = {
    **A_SPAWN_THAT_DIED,
    "stderr": "Invalid configuration: 'entry' must be an array\n",
}


def _broke_at(tmp_path: Path, tool: str, exit_code: int) -> bool:
    project = a_project_whose_tool(tmp_path, tool, f"process.exit({exit_code});\n")
    return ask_the_seam(project, tool)["broke"]


def test_a_tool_that_failed_without_a_word_is_named_along_with_its_exit(
    tmp_path: Path,
) -> None:
    project = a_project_whose_tool(tmp_path, "wordless", SAYS_NOTHING)

    answer = ask_the_seam(project, "wordless")

    assert answer["broke"] is True
    assert answer["complaint"] == "wordless: exited 2 without a word of its own\n"


def test_a_tool_killed_mid_report_is_named_along_with_the_signal(
    tmp_path: Path,
) -> None:
    """The complaint stays one sentence, whatever the tool had already printed.

    A killed tool leaves no exit code, so it has to be described by its signal;
    its whitespace-only stderr is not words; and the report it was halfway
    through is not a diagnosis. Carrying that report instead would put every
    flushed byte into a reading agent's context, and it arrives as one line, so
    nothing downstream can trim it.
    """
    project = a_project_whose_tool(tmp_path, "culled", KILLED_MID_REPORT)

    answer = ask_the_seam(project, "culled")

    assert answer["printed"] == PARTIAL_REPORT_BYTES, "the fixture never flushed"
    assert answer["broke"] is True
    assert answer["complaint"] == "culled: killed by SIGKILL without a word of its own\n"


def test_a_tool_that_diagnosed_itself_is_quoted_in_its_own_words(
    tmp_path: Path,
) -> None:
    project = a_project_whose_tool(tmp_path, "knip", COMPLAINS)

    answer = ask_the_seam(project, "knip")

    assert answer["complaint"] == "knip.json: line 3 is nonsense\n"


def test_the_words_a_tool_got_out_outrank_the_spawns_own_error(
    tmp_path: Path,
) -> None:
    """A run can both break and be explained: the tool diagnosed itself before
    the spawn went down. Its own words win, because `spawnSync`'s name the node
    that was spawned and leave the reader with nothing to act on."""
    answer = judge(tmp_path, "knip", A_SPAWN_THAT_DIED_AFTER_SPEAKING)

    assert answer["broke"] is True
    assert answer["complaint"] == A_SPAWN_THAT_DIED_AFTER_SPEAKING["stderr"]


def test_a_spawn_that_died_without_words_names_the_tool_not_the_runtime(
    tmp_path: Path,
) -> None:
    answer = judge(tmp_path, "noisy", A_SPAWN_THAT_DIED)

    assert answer["broke"] is True
    assert answer["complaint"].startswith("noisy: ")
    assert "ENOBUFS" in answer["complaint"]


def test_a_tool_nobody_installed_is_named_once_in_the_shells_own_phrase(
    tmp_path: Path,
) -> None:
    """The phrase the runner coaches on (``part_output.COMMAND_NOT_FOUND``).
    The seam already said the tool's name here, so saying it again would leave
    the one first-contact failure with an obvious fix reading as a stutter."""
    project = tmp_path / "bare"
    project.mkdir()
    (project / "package.json").write_text('{"name": "demo"}', encoding="utf-8")

    answer = ask_the_seam(project, "eslint")

    assert answer["complaint"] == "eslint: command not found\n"


def test_a_findings_exit_is_not_breakage(tmp_path: Path) -> None:
    """Both tools this seam runs exit 1 for "I found something to report" — the
    commonest successful run there is — so breakage starts above it."""
    assert _broke_at(tmp_path, "clean", 0) is False
    assert _broke_at(tmp_path, "reporting", 1) is False
    assert _broke_at(tmp_path, "broken", 2) is True


def test_a_spawn_that_never_started_is_answered_rather_than_read(
    tmp_path: Path,
) -> None:
    """There are no streams here at all, not empty ones — so asking this run
    what it said has to survive the asking. Reaching for `.trim()` on the
    absent stderr throws a `TypeError`, which is an unhandled Node traceback in
    the one place whose whole job is to produce a sentence instead."""
    answer = judge(tmp_path, "eslint", A_SPAWN_THAT_NEVER_STARTED)

    assert answer["broke"] is True
    assert answer["complaint"].startswith("eslint: ")
    assert "E2BIG" in answer["complaint"]
