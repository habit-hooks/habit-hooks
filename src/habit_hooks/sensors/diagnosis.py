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

    Truncating is only worth doing when it produces something shorter than what
    it replaces: the excerpt is the head, the elision line standing in for what
    it hides, and the tail, so it earns its place only once that is fewer lines
    than the input it would replace.
    """
    lines = diagnosis.splitlines()
    head = DIAGNOSIS_LINE_LIMIT // 2
    tail = DIAGNOSIS_LINE_LIMIT - head
    omitted = len(lines) - head - tail
    excerpt = [*lines[:head], f"... {omitted} lines omitted ...", *lines[-tail:]]
    if len(excerpt) < len(lines):
        return "\n".join(excerpt)
    return diagnosis
