"""Every text-mode ``read_text()``/``write_text()``/``open()`` call in this
project names its own encoding (issue #133).

Python decodes text-mode I/O in the platform's locale unless told otherwise --
cp1252 on Windows, and (per ``test_ascii_locale_regressions.py``) even plain
C/POSIX on a Mac. The guides, spec files and configs this tool reads and
writes are UTF-8 regardless of what the runtime's locale says text is, so a
call site that omits ``encoding="utf-8"`` is a latent copy of that bug. This
walks every ``.py`` file this project owns as its own text-I/O surface and
fails on the first call that regresses -- the gate that stops the bug coming
back one call site at a time.

What counts as a violation is ``text_io_encoding.py``, exercised on its own in
``test_text_io_encoding_detector.py``; this file only decides which files the
repo holds to that.
"""

from __future__ import annotations

from pathlib import Path

from text_io_encoding import REPO_ROOT, _violations_in_file

# A floor below the project's own file count (128 at the time this was
# written): protects against `_target_files()` resolving to nothing -- a
# typo'd glob, a moved directory -- which would otherwise pass this gate with
# no calls scanned and no violations to report.
MINIMUM_TARGET_FILES = 50


def _target_files() -> list[Path]:
    """Every ``.py`` file under this project's own text-I/O surface.

    Each plugin's own ``tests/`` is included alongside its ``src/``: issue
    #133's ASCII-locale suite run failed here first, in a plugin test helper
    the original sweep had missed by scoping to ``src/`` alone.
    """
    roots = [
        REPO_ROOT / "src",
        REPO_ROOT / "tests",
        *(REPO_ROOT / "plugins").glob("*/src"),
        *(REPO_ROOT / "plugins").glob("*/tests"),
    ]
    files = [path for root in roots for path in root.rglob("*.py")]
    files.append(REPO_ROOT / "conftest.py")
    return files


def test_target_files_resolve_to_a_nontrivial_set() -> None:
    """A misconfigured root -- a typo'd glob, a moved directory -- must fail
    loud rather than let the gate below pass over zero files with nothing to
    scan and nothing to report."""
    assert len(_target_files()) > MINIMUM_TARGET_FILES


def test_every_text_io_call_in_the_repo_names_its_encoding() -> None:
    violations = [line for path in _target_files() for line in _violations_in_file(path)]
    assert violations == [], (
        "these calls read or write text with no encoding= (issue #133):\n"
        + "\n".join(violations)
    )
