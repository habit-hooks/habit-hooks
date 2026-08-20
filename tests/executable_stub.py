"""Write a tool stub the platform actually running the test would accept.

``shutil.which`` and a real spawn are OS mechanics no ``host_platform`` seam
reaches (see ``platform_probe``'s own note on this): Windows only considers a
name matching ``PATHEXT`` executable at all, so an extensionless file with a
``#!/bin/sh`` shebang -- what a POSIX install looks like -- is invisible to
it, on any machine, however ``host_platform.is_windows()`` is pinned. There is
nothing to pin here, because the expected answer at every call site is the
same on both platforms; what has to change is the stub's own shape, decided
by the real host (``os.name``), not the one a test is pretending to run on.

A ``.cmd`` is still genuinely spawnable without a shell: Windows'
``CreateProcess`` recognises the extension and runs it through ``cmd.exe``
itself, the same way it would a real installed console-script shim -- no
``shell=True`` needed on the caller's side, which is what lets these stand in
for a real install rather than for a shell recipe.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

_ON_WINDOWS = os.name == "nt"


def write_stub(bin_dir: Path, name: str, exit_code: int = 0) -> None:
    """An executable ``name`` that does nothing but exit ``exit_code``."""
    if _ON_WINDOWS:
        _write(bin_dir, f"{name}.cmd", f"@echo off\r\nexit /b {exit_code}\r\n")
        return
    _write_posix(bin_dir, name, f"#!/bin/sh\nexit {exit_code}\n")


def write_batch_stub(bin_dir: Path, name: str) -> Path:
    """An executable ``<name>.cmd`` this host will run, and the path to it.

    ``write_stub`` spells a name the way an install on that platform would, so
    off Windows it carries no extension at all — and an extension is the whole
    of what a batch file is recognised by. This one spells it deliberately: on
    Windows that is a real batch file, run through ``cmd.exe``, and everywhere
    else it is an ordinary shebang script whose name happens to end the same
    way. Both are what the guard reads, which is why it can be shown on either.
    """
    tool = bin_dir / f"{name}.cmd"
    if _ON_WINDOWS:
        _write(bin_dir, tool.name, "@echo off\r\nexit /b 0\r\n")
    else:
        _write_posix(bin_dir, tool.name, "#!/bin/sh\nexit 0\n")
    return tool


def write_wedged_tool(bin_dir: Path, name: str, seconds: int = 5) -> None:
    """An executable ``name`` that never answers inside ``seconds``."""
    if _ON_WINDOWS:
        # `ping` is the standard sleep-substitute on Windows -- one probe with
        # no delay, then a one-second gap per remaining count -- and lives in
        # `System32`, which `cmd.exe` finds regardless of this test's `PATH`.
        _write(
            bin_dir,
            f"{name}.cmd",
            f"@echo off\r\nping -n {seconds + 1} 127.0.0.1 >nul\r\n",
        )
        return
    # `sleep` is spelled absolutely, and run via `exec`, for the same reason
    # `write_recording_tool` avoids `dirname`: the `PATH` this runs on is
    # empty by design, and `exec` puts the deadline on the sleep itself
    # rather than the shell holding it.
    _write_posix(bin_dir, name, f"#!/bin/sh\nexec /bin/sleep {seconds}\n")


def write_recording_tool(bin_dir: Path, name: str, log_name: str) -> None:
    """An executable ``name`` that records its args and its cwd, one per
    line, to ``log_name`` in its own directory."""
    if _ON_WINDOWS:
        _write_recording_windows(bin_dir, name, log_name)
        return
    # Builtins and parameter expansion only: the `PATH` this runs on is empty
    # by design, so a stub reaching for `dirname` would fail before it
    # recorded anything.
    _write_posix(
        bin_dir,
        name,
        f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "${{0%/*}}/{log_name}"\n'
        f'pwd >> "${{0%/*}}/{log_name}"\n',
    )


def _write_recording_windows(bin_dir: Path, name: str, log_name: str) -> None:
    """A ``.cmd`` that hands its args and cwd to a companion Python helper.

    `cmd.exe`'s own `%*` preserves what it is given verbatim, backslash
    escaping included, rather than re-splitting it -- so it is handed
    straight to a second CRT-argv-parsing program (this interpreter) that
    undoes exactly the escaping `subprocess`'s own `list2cmdline` applied to
    build that command line in the first place. A bare `echo %*` would leave
    the escaping in, which nothing downstream expects.
    """
    log_path = bin_dir / log_name
    helper = bin_dir / f"_{name}_recorder.py"
    _write(
        bin_dir,
        helper.name,
        "import pathlib, sys\n"
        f"log = pathlib.Path({str(log_path)!r})\n"
        "log.write_text(\n"
        "    ' '.join(sys.argv[1:]) + '\\n' + str(pathlib.Path.cwd()) + '\\n',\n"
        "    encoding='utf-8',\n"
        ")\n",
    )
    _write(
        bin_dir,
        f"{name}.cmd",
        f'@echo off\r\n"{sys.executable}" "{helper}" %*\r\n',
    )


def _write(bin_dir: Path, filename: str, body: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / filename).write_text(body, encoding="utf-8")


def _write_posix(bin_dir: Path, name: str, body: str) -> None:
    _write(bin_dir, name, body)
    tool = bin_dir / name
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
