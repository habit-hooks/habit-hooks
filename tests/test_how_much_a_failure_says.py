"""How much of a failing part's own words the notice carries back.

``diagnosis.py``'s question, and a separate one from which failure is being
described (``test_part_output.py``). habit-hooks writes into a coding agent's
context, so a tool with a great deal to say is bounded two ways — by lines, and
within a line — while one with little to say is quoted whole.
"""

from __future__ import annotations

from pathlib import Path

from sensor_notice import script_notice

import pytest

from habit_hooks.sensors import diagnosis
from habit_hooks.sensors.diagnosis import (
    DIAGNOSIS_LINE_LIMIT,
    DIAGNOSIS_LINE_LENGTH_LIMIT,
    keep_both_ends,
)


def test_a_sensor_at_the_truncation_boundary_is_still_quoted_whole(
    tmp_path: Path,
) -> None:
    """Truncating only pays for itself once the excerpt it produces — head, an
    elision line, and tail — is actually shorter than the diagnosis it would
    replace. At 21 lines the excerpt would also come to 21 lines, so nothing is
    dropped, and nothing is lost for free."""
    notice = script_notice(
        tmp_path,
        "import sys\n"
        "for i in range(1, 22):\n"
        "    print(f'line {i}', file=sys.stderr)\n"
        "sys.exit(1)\n",
    )
    lines = notice.splitlines()

    assert "line 1" in lines
    assert "line 21" in lines
    assert "omitted" not in notice


def test_a_sensor_one_line_past_the_boundary_finally_elides(tmp_path: Path) -> None:
    """One line more and the excerpt is finally shorter than the diagnosis it
    replaces, so it elides — head, tail, and the middle it stands in for."""
    notice = script_notice(
        tmp_path,
        "import sys\n"
        "for i in range(1, 23):\n"
        "    print(f'line {i}', file=sys.stderr)\n"
        "sys.exit(1)\n",
    )
    lines = notice.splitlines()

    assert "line 1" in lines
    assert "line 11" not in lines
    assert "line 22" in lines
    assert "... 2 lines omitted ..." in lines


def test_a_sensor_whose_last_line_carries_the_diagnosis_still_quotes_it(
    tmp_path: Path,
) -> None:
    """A Python traceback names its exception on its *last* line, not its first.

    A chatty tool that dies with a traceback — the shape every Python-helper
    sensor's own crash takes, deptry included — buries its one useful line at
    the bottom of output that easily runs past the quoted budget. Quoting only
    the head, as this once did, guarantees that line is exactly the one
    dropped; the tail has to survive too.
    """
    notice = script_notice(
        tmp_path,
        "import sys\n"
        "for i in range(1, 25):\n"
        '    print(f"noise {i}", file=sys.stderr)\n'
        'raise RuntimeError("boom: the real reason")\n',
    )

    assert "boom: the real reason" in notice


def test_a_sensor_that_says_it_all_on_one_line_is_still_cut_down(
    tmp_path: Path,
) -> None:
    """A budget counted in lines bounds a chatty tool, not a terse one.

    ``eslint -f json`` is a single line however many megabytes it holds, so a
    tool that dies printing one clears a twenty-line limit without shedding a
    byte — and the whole of it lands in a notice habit-hooks writes into a
    coding agent's context, which is the cost this budget exists to bound.
    """
    notice = script_notice(
        tmp_path,
        "import sys\n"
        "print('S' * 2_000_000 + 'THE REAL COMPLAINT', file=sys.stderr)\n"
        "sys.exit(1)\n",
    )

    assert len(notice) < 10_000, f"notice carried {len(notice)} characters"
    assert "THE REAL COMPLAINT" in notice, "the end of the line is the punchline"
    assert "omitted" in notice, "and it says the middle was dropped"


def test_a_line_exactly_at_its_budget_is_quoted_whole(tmp_path: Path) -> None:
    """Cutting is only worth doing once there is something to cut."""
    notice = script_notice(
        tmp_path,
        "import sys\n"
        f"print('S' * {DIAGNOSIS_LINE_LENGTH_LIMIT}, file=sys.stderr)\n"
        "sys.exit(1)\n",
    )

    assert "S" * DIAGNOSIS_LINE_LENGTH_LIMIT in notice
    assert "omitted" not in notice


def test_cutting_a_line_never_makes_it_longer() -> None:
    """A line just past the budget costs more to elide than it saves.

    The elision has to say how much it hides, and that sentence is longer than
    the handful of characters an only-just-oversized line has to give up — so
    quoting it whole is both shorter and more use. The line budget already
    works this way; this is the same economy one scale down, and without it
    every line from one past the budget to about thirty past came back *longer*
    than it went in, announcing ``1 characters omitted``.

    Asked of the budget rather than of a hard-coded boundary: where cutting
    starts to pay follows from the elision's own length, so a reworded elision
    must not become a silently wrong boundary.
    """
    over = range(DIAGNOSIS_LINE_LENGTH_LIMIT, DIAGNOSIS_LINE_LENGTH_LIMIT + 100)

    for length in over:
        quoted = keep_both_ends("x" * length)
        assert len(quoted) <= length, f"{length} characters came back as {len(quoted)}"


def test_a_line_far_past_its_budget_keeps_both_of_its_ends() -> None:
    """Far enough past it, the middle is worth dropping — and both ends live.

    Which end carries the complaint is no more predictable inside a line than
    across a stack trace: a tool that dumps what it was reading and then says
    why puts the reason last.
    """
    quoted = keep_both_ends("HEAD" + "x" * 5_000 + "TAIL")

    assert quoted.startswith("HEAD")
    assert quoted.endswith("TAIL")
    assert "characters omitted" in quoted
    assert len(quoted) < 1_100


def test_only_the_lines_that_survive_are_cut_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The work is bounded by the budget, not by how much the tool said.

    Cutting every line before choosing which twenty to keep costs a second copy
    of the whole input — on the megabytes this module exists to bound, that is
    tens of megabytes allocated to produce twenty thousand characters. Choosing
    first makes the cost the same for a stderr of ten lines and one of ten
    million, which is measured here as how many lines are ever looked at.
    """
    cut = diagnosis._both_ends_of
    seen = []
    monkeypatch.setattr(
        diagnosis, "_both_ends_of", lambda line: seen.append(line) or cut(line)
    )

    diagnosis.keep_both_ends("\n".join("x" * 2_000 for _ in range(10_000)))

    assert len(seen) <= DIAGNOSIS_LINE_LIMIT + 1, f"cut {len(seen)} lines down"
