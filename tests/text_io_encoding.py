"""Whether one AST ``Call`` is a text-mode I/O call that names no encoding
(issue #133): ``read_text``/``write_text``, ``open()``/``.open()`` in text
mode, or a subprocess call reading decoded output via ``text=True`` /
``universal_newlines=True``.

``test_text_io_encoding_detector.py`` is this detector's own coverage;
``test_text_io_names_its_encoding.py`` is the repo-wide gate that asks it of
every call site this project owns.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
READ_WRITE_METHODS = ("read_text", "write_text")
SUBPROCESS_TEXT_CALLS = ("run", "Popen", "check_output")
TEXT_MODE_KEYWORDS = ("text", "universal_newlines")


def _call_kind(call: ast.Call) -> str | None:
    """"read_write" for ``.read_text()``/``.write_text()``, "open" for
    ``open()``/``.open()``, "subprocess_text" for ``run()``/``Popen()``/
    ``check_output()`` (bare or ``subprocess.``-qualified -- like ``.open()``,
    checked whatever the receiver is), ``None`` for anything else this gate
    ignores."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in READ_WRITE_METHODS:
        return "read_write"
    if isinstance(func, ast.Attribute) and func.attr == "open":
        return "open"
    if isinstance(func, ast.Name) and func.id == "open":
        return "open"
    if isinstance(func, ast.Attribute) and func.attr in SUBPROCESS_TEXT_CALLS:
        return "subprocess_text"
    if isinstance(func, ast.Name) and func.id in SUBPROCESS_TEXT_CALLS:
        return "subprocess_text"
    return None


def _mode_argument(call: ast.Call) -> ast.expr | None:
    """The AST node for this ``open()``-shaped call's mode argument, or
    ``None`` when it named none.

    The mode's position depends on which spelling this is: ``open(path, mode)``
    puts it at ``args[1]``, but ``path.open(mode)`` has no separate ``path``
    argument -- the receiver isn't positional -- so there it is ``args[0]``.
    Scanning every positional argument for a "b" (the previous shape of this
    check) treated any path containing a "b" as a mode, exempting
    ``open(".habit-hooks/config.toml")`` from the gate it exists to enforce.
    """
    keyword = next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
    if keyword is not None:
        return keyword
    index = 0 if isinstance(call.func, ast.Attribute) else 1
    return call.args[index] if len(call.args) > index else None


def _mode_argument_is_binary(call: ast.Call) -> bool:
    """Whether an ``open()``-shaped call's mode argument contains "b" --
    ``read_bytes``'s equivalent, which needs no encoding."""
    mode = _mode_argument(call)
    return (
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and "b" in mode.value
    )


def _has_encoding_kwarg(call: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in call.keywords)


def _requests_text_mode(call: ast.Call) -> bool:
    """Whether a subprocess call asked for decoded output via ``text=True`` or
    the older ``universal_newlines=True`` -- the only way such a call decodes
    anything, and so the only way it needs an ``encoding=`` of its own."""
    return any(
        kw.arg in TEXT_MODE_KEYWORDS
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for kw in call.keywords
    )


def _is_violation(call: ast.Call) -> bool:
    kind = _call_kind(call)
    if kind is None:
        return False
    if kind == "open" and _mode_argument_is_binary(call):
        return False
    if kind == "subprocess_text" and not _requests_text_mode(call):
        return False
    return not _has_encoding_kwarg(call)


def _violation_lines(tree: ast.AST) -> list[int]:
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and _is_violation(node)]


def _violations_in_source(source: str) -> list[int]:
    return _violation_lines(ast.parse(source))


def _violations_in_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [f"{path.relative_to(REPO_ROOT)}:{lineno}" for lineno in _violation_lines(tree)]
