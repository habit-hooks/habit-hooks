"""How much of a failing part's own words to carry back, and how to read them.

A part that diagnosed its own failure — the missing base ref
`snooze-until-changed` names, the npm package a sensor could not `require` — is
the one thing a pipeline user can act on, and its stderr is otherwise thrown
away. But habit-hooks writes into a coding agent's context, and a tool that dies
mid-warning-storm can produce megabytes of it.

What is worth carrying is therefore a question of its own, asked the same way of
every failure that said anything at all — which is what separates it from
``part_output.py``, whose subject is *which* failure is being described and how
this run names it. The dependency runs one way (``part_output`` → here).
"""

from __future__ import annotations

# How much of a failing part's own output is quoted back, split evenly between
# the start and the end. habit-hooks writes to a coding agent's context, and a
# tool that dies mid-warning-storm can produce megabytes — but a Python
# traceback names its exception on the *last* line, so the head alone is
# guaranteed to be the one part carrying no diagnosis.
DIAGNOSIS_LINE_LIMIT = 20

# How much of any single line survives, split the same way. Counting lines
# alone bounds a tool that is chatty and not one that is terse: a report from
# ``eslint -f json`` is ONE line however many megabytes it holds, so it clears
# a twenty-line budget without shedding a byte.
#
# Generous enough for every diagnosis a wrapped tool writes for a human to read.
# Measured, longest stderr line on a real failure: pmd 273, eslint 221, deptry
# 207, ruff 199, a Node stack frame 170, a Python traceback frame 154, knip 76,
# ``command not found`` 42. This tool's own longest refusal is around 400.
#
# What it does cut is a machine-readable report a helper forwards when its tool
# said nothing else — phpmd answers a parse error with JSON whose ``message``
# carries a whole escaped PHP stack trace, one line of nearly 7,000 characters.
# Cutting that is the point, and both ends of it survive: the file and position
# are in the first 200 characters and ``#23 {main}`` is at the end.
#
# The two limits together cap a notice at about 20,000 characters — which is
# three to four times that in bytes once a tool complains in CJK or emoji.
DIAGNOSIS_LINE_LENGTH_LIMIT = 1_000


def as_text(output: str | bytes | None) -> str:
    """A killed part's output as text, whatever the spawn was told to decode.

    ``deadline.py`` reads the killed command's pipe and hands over text, but the
    expiry it falls back to where that pipe will not close carries the raw bytes
    ``TimeoutExpired`` has always held. Undecodable bytes are replaced rather
    than raised on, because this runs inside the handler reporting the failure.
    """
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""


def keep_both_ends(diagnosis: str) -> str:
    """Both ends of a part's complaint, saying so when the middle was dropped.

    A Python traceback's exception line — the one line that says what actually
    broke — is its *last* line, not its first. Quoting only the head, as this
    once did, therefore quotes back the one part of a traceback that carries no
    diagnosis whenever the part is chatty enough to exceed the budget. Keeping
    a tail too means the punchline survives whichever end of the output it
    landed on.

    A line too long for its own budget is cut the same way, for the same
    reason, once the surviving lines are chosen — a tool can be verbose in
    either direction and one of them is a single enormous line.

    Truncating is only worth doing when it produces something shorter than what
    it replaces: an excerpt is the head, the elision standing in for what it
    hides, and the tail, so it earns its place only once that is smaller than
    the input it would replace. Both cuts obey that, which is also what keeps
    the elision's count from ever being small enough to read as ``1 lines``.
    """
    lines = diagnosis.splitlines()
    kept = [_both_ends_of(line) for line in _the_lines_worth_keeping(lines)]
    return diagnosis if kept == lines else "\n".join(kept)


def _the_lines_worth_keeping(lines: list[str]) -> list[str]:
    """Both ends of ``lines``, or all of them when eliding would not be shorter.

    Chosen before any line is cut down, so a stderr of megabytes costs one pass
    to slice rather than a second copy of itself to shorten — the input this
    whole module exists to bound is exactly the one where that matters.
    """
    head = DIAGNOSIS_LINE_LIMIT // 2
    tail = DIAGNOSIS_LINE_LIMIT - head
    omitted = len(lines) - head - tail
    excerpt = [*lines[:head], f"... {omitted} lines omitted ...", *lines[-tail:]]
    return excerpt if len(excerpt) < len(lines) else lines


def _both_ends_of(line: str) -> str:
    """One line cut to its budget, by the same rule and for the same reason.

    Where the punchline lands is no more predictable within a line than across
    them — a tool that appends its real complaint to a dump of what it was
    reading puts it at the very end — so this keeps both ends here too.
    """
    head = DIAGNOSIS_LINE_LENGTH_LIMIT // 2
    tail = DIAGNOSIS_LINE_LENGTH_LIMIT - head
    omitted = len(line) - head - tail
    excerpt = f"{line[:head]}... {omitted} characters omitted ...{line[-tail:]}"
    return excerpt if len(excerpt) < len(line) else line
