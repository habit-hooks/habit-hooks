"""Why a run scanned nothing, in one line the reader can act on.

Silence about a run that measured nothing is indistinguishable from a clean one,
so every empty scope that is not an error still says which setting emptied it.
Split from ``scope.py`` because deciding what to scan and explaining what was not
scanned answer different questions — and the explanation is where the wording, of
which there is more than there is code, has to stay consistent.

Two shapes, one setting: a whole run that narrowed to nothing gets
``NO_FILES_NOTICE``, while ``--file`` keeps a per-file diagnosis (the hook behind
it fires on every edit, including files a project rightly does not scan).
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .project_paths import project_relative

# Discovery is opt-in (#97): a project that names no source scans nothing.
_NO_FILES = "no [files] are configured — name what to scan in .habit-hooks/config.toml"
NO_FILES_NOTICE = f"habit-sensors: {_NO_FILES}; nothing scanned"


def empty_scope_notices(
    named: str | None, project_dir: Path, config: Config
) -> list[str]:
    """Why a scope came out empty: the diagnosis for the one file ``--file``
    named, else the whole run's. Only an empty scope is ever remarked on."""
    if named is not None:
        return [_named_file_notice(named, project_dir, config)]
    return [NO_FILES_NOTICE] if config.files is None else []


def _named_file_notice(named: str, project_dir: Path, config: Config) -> str:
    """Which of the three ways ``--file`` scanned nothing this was.

    With no ``[files]`` at all there is no section for the file to be outside of,
    so it names the missing setting rather than a phantom one — the same wording
    ``NO_FILES_NOTICE`` uses, about the one file the hook asked after.
    """
    placed = project_relative(named, project_dir)
    if placed is None or not (project_dir / placed).is_file():
        reason = " is not a file in this project"
    elif config.files is None:
        reason = f": {_NO_FILES}"
    else:
        reason = " is outside [files]"
    return f"habit-sensors: --file {named!r}{reason}; nothing scanned"
