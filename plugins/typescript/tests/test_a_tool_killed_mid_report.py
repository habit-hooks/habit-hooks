"""What the seam makes of a tool killed while it was still reporting.

The answer is a different fact on each platform, so each half runs where it can
be told. POSIX ends a process with a signal, and the parent reads
``status: null, signal: "SIGKILL"`` — a run that plainly never finished. Windows
has no signals: Node's ``process.kill`` there calls ``TerminateProcess``, and
the parent reads an ordinary ``status: 1`` with no signal, which is exactly what
eslint and knip look like when they exit 1 because they found something to
report.

That asymmetry is the whole reason both halves are written down. On POSIX the
seam catches it; on Windows nothing at this level can, and what saves the run is
the sensor one layer out refusing output it cannot read
(``test_both_node_sensors_refuse_alike.py``). Asserting only the half this
machine happens to run would leave the other silently unexamined, which is how
Windows CI came to be the first thing to notice.
"""

from __future__ import annotations

from pathlib import Path

from platform_probe import A_MACHINE_WITH_SIGNALS, A_MACHINE_WITHOUT_SIGNALS
from project_tool_probe import a_project_whose_tool, ask_the_seam, run

# Comfortably past a pipe's own 64KB buffer, so the report really is in flight
# rather than sitting in the tool. Nothing here needs the megabytes the OOM
# killer would really have let through: what matters is that the complaint does
# not grow with it.
PARTIAL_REPORT_BYTES = 100_000

SENSORS = Path(__file__).parents[1] / "src" / "habit_hooks_typescript" / "sensors"

# A tool the OOM killer reached on a big repository, after it had flushed most
# of a report: a large half-written stdout and a stderr holding nothing but
# whitespace. One stub, killed the same way on both platforms — what the
# parent then reads is what differs, and is what each case below states.
# `fs.writeSync` rather than `process.stdout.write` so the bytes are really in
# the pipe before the kill lands: a write still queued inside the tool would
# make either case pass for the wrong reason.
KILLED_MID_REPORT = (
    'const fs = require("node:fs");\n'
    f'fs.writeSync(1, "[".padEnd({PARTIAL_REPORT_BYTES}, "x"));\n'
    'fs.writeSync(2, "  \\n");\n'
    'process.kill(process.pid, "SIGKILL");\n'
)


@A_MACHINE_WITH_SIGNALS
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
    assert (answer["status"], answer["signal"]) == (None, "SIGKILL")
    assert answer["broke"] is True
    assert answer["complaint"] == "culled: killed by SIGKILL without a word of its own\n"


@A_MACHINE_WITH_SIGNALS
def test_a_sensor_whose_tool_was_killed_says_so_by_its_signal(tmp_path: Path) -> None:
    """What a reader gets, on the platform where the seam is what caught it."""
    project = a_project_whose_tool(tmp_path, "knip", KILLED_MID_REPORT)

    result = run(["node", str(SENSORS / "knip.cjs")], project)

    assert result.returncode != 0
    assert result.stderr == "knip: killed by SIGKILL without a word of its own\n"


@A_MACHINE_WITHOUT_SIGNALS
def test_a_tool_killed_mid_report_looks_exactly_like_a_findings_run(
    tmp_path: Path,
) -> None:
    """The same kill, answered for the platform that has no signals.

    Node's `process.kill` on Windows is `TerminateProcess`, so the parent reads
    an ordinary exit 1 and no signal — indistinguishable from eslint or knip
    exiting 1 because they found something to report. This seam does not guess:
    it reads exit 1 as a findings run, which is the right reading of the only
    evidence there is.

    What stops the half-written report reaching `JSON.parse` is therefore not
    here but one layer out, where the sensor refuses output it cannot read
    (`test_both_node_sensors_refuse_alike.py`). Stated rather than skipped,
    because a platform gap nothing reports is one nobody closes.
    """
    project = a_project_whose_tool(tmp_path, "culled", KILLED_MID_REPORT)

    answer = ask_the_seam(project, "culled")

    assert answer["printed"] == PARTIAL_REPORT_BYTES, "the fixture never flushed"
    assert (answer["status"], answer["signal"]) == (1, None)
    assert answer["broke"] is False


@A_MACHINE_WITHOUT_SIGNALS
def test_a_sensor_whose_tool_was_killed_still_refuses_its_half_report(
    tmp_path: Path,
) -> None:
    """The same, on the platform where the seam could not tell.

    Nothing upstream of the parse knows this run died, so this is the assertion
    that the half-written report never reaches `JSON.parse` — with a real kill
    rather than the stub that stands in for one everywhere else.
    """
    project = a_project_whose_tool(tmp_path, "knip", KILLED_MID_REPORT)

    result = run(["node", str(SENSORS / "knip.cjs")], project)

    assert result.returncode != 0
    assert result.stderr == (
        "knip: exited 1, and what it printed is not a report this sensor can read\n"
    )
