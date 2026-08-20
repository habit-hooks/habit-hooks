"""The text-I/O-encoding detector's own coverage: ZOMBIES over the
``open()``/``read_text()`` interface split and the boundary between text and
binary mode, one call shape at a time.

What each call shape means is ``text_io_encoding.py``; the repo-wide gate that
puts the detector to every file this project owns is
``test_text_io_names_its_encoding.py``.
"""

from __future__ import annotations

from text_io_encoding import _violations_in_source

# -- the detector's own cases (ZOMBIES: zero/one args, the open()/read_text()
# interface split, and the boundary between text and binary mode) ----------


def test_read_text_with_no_args_and_no_encoding_is_a_violation() -> None:
    assert _violations_in_source("path.read_text()") == [1]


def test_read_text_naming_encoding_is_clean() -> None:
    assert _violations_in_source('path.read_text(encoding="utf-8")') == []


def test_write_text_with_content_but_no_encoding_is_a_violation() -> None:
    assert _violations_in_source("path.write_text(content)") == [1]


def test_builtin_open_in_default_text_mode_is_a_violation() -> None:
    assert _violations_in_source("open(path)") == [1]


def test_builtin_open_naming_encoding_is_clean() -> None:
    assert _violations_in_source('open(path, encoding="utf-8")') == []


def test_builtin_open_in_binary_mode_needs_no_encoding() -> None:
    assert _violations_in_source('open(path, "rb")') == []


def test_path_dot_open_in_binary_mode_needs_no_encoding() -> None:
    assert _violations_in_source('path.open("rb")') == []


def test_path_dot_open_in_text_mode_with_no_encoding_is_a_violation() -> None:
    assert _violations_in_source('path.open("r")') == [1]


def test_open_with_a_binary_mode_keyword_needs_no_encoding() -> None:
    assert _violations_in_source('open(path, mode="wb")') == []


def test_a_path_containing_b_is_still_a_violation_with_no_encoding() -> None:
    """A "b" in the *path*, not the mode, must not read as binary mode -- the
    false negative that let ``open(".habit-hooks/config.toml")`` (this tool's
    own config directory) slip past the gate it exists to enforce."""
    assert _violations_in_source('open("build/report.txt")') == [1]


def test_a_call_named_open_that_is_not_open_is_still_checked() -> None:
    """``.open()`` is checked whatever the receiver is -- this gate does not
    try to prove the receiver is a ``Path``, matching how rare and deliberate
    every other ``.open()`` call in this project already is (see the docstring
    above): a false positive here costs one ``encoding=``, a false negative
    lets #133 back in."""
    assert _violations_in_source('socket.open("r")') == [1]


def test_an_unrelated_call_is_not_flagged() -> None:
    assert _violations_in_source("subprocess.run(cmd)") == []


# -- subprocess text mode (issue #133 covers 33 call sites like this one; a
# kind that only recognised read_text/write_text/open left every one of them
# unguarded) --------------------------------------------------------------


def test_subprocess_run_with_no_text_mode_is_not_flagged() -> None:
    assert _violations_in_source("subprocess.run(cmd, text=False)") == []


def test_subprocess_run_with_text_true_and_no_encoding_is_a_violation() -> None:
    assert _violations_in_source("subprocess.run(cmd, text=True)") == [1]


def test_subprocess_run_with_text_true_and_encoding_is_clean() -> None:
    assert _violations_in_source('subprocess.run(cmd, text=True, encoding="utf-8")') == []


def test_subprocess_run_with_universal_newlines_and_no_encoding_is_a_violation() -> None:
    assert _violations_in_source("subprocess.run(cmd, universal_newlines=True)") == [1]


def test_popen_with_text_true_and_no_encoding_is_a_violation() -> None:
    assert _violations_in_source("subprocess.Popen(cmd, text=True)") == [1]


def test_check_output_with_text_true_and_no_encoding_is_a_violation() -> None:
    assert _violations_in_source("subprocess.check_output(cmd, text=True)") == [1]


def test_a_bare_run_with_text_true_and_no_encoding_is_still_checked() -> None:
    """``run``/``Popen``/``check_output`` are checked whatever the receiver is,
    the same as ``.open()`` above -- a project importing them bare (``from
    subprocess import run``) must not go unguarded."""
    assert _violations_in_source("run(cmd, text=True)") == [1]
