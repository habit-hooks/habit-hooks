"""Why a run scanned nothing, in one line the reader can act on.

Silence about a run that measured nothing is indistinguishable from a clean one,
so every empty scope that is not an error still says which setting emptied it.
Split from ``scope.py`` because deciding what to scan and explaining what was not
scanned answer different questions — and the explanation is where the wording, of
which there is more than there is code, has to stay consistent.

Two shapes, one setting: a whole run that narrowed to nothing gets
``NO_FILES_NOTICE``, while ``--file`` keeps a per-file diagnosis (the hook behind
it fires on every edit, including files a project rightly does not scan).

A submodule is the one thing said about a scope that is *not* empty: the scan
shrank without emptying, and the gap has to be named or the run renders ✅ over
it. Every notice here is advisory — written to stderr, leaving the exit code to
the findings — which is why a run that scanned nothing at all still exits 0.
"""

from __future__ import annotations

from pathlib import Path

from . import git_listing
from .config import Config
from .path_globs import matching
from .project_paths import project_relative

# Discovery is opt-in (#97): a project that names no source scans nothing.
_NO_FILES = "no [files] are configured — name what to scan in .habit-hooks/config.toml"
NO_FILES_NOTICE = f"habit-sensors: {_NO_FILES}; nothing scanned"

# A `[files]` that is set and still kept nothing. Both halves of the cause are
# named because neither is visible from the other: `[files]` may be too narrow,
# or git may be ignoring the very tree it was written for.
NOTHING_MATCHED_NOTICE = (
    "habit-sensors: nothing matched [files] — check it in "
    ".habit-hooks/config.toml, and whether git ignores the paths you expected; "
    "nothing scanned"
)


def empty_scope_notices(
    named: str | None, project_dir: Path, config: Config
) -> list[str]:
    """Why a scope came out empty: the diagnosis for the one file ``--file``
    named, else the whole run's. Only an empty scope is ever remarked on.

    **Every** empty scope says something, and that is the point. A ``[files]``
    that is set and matched nothing used to be the one silent case, so a project
    whose ``.gitignore`` covered its own source tree scanned zero files and
    rendered ✅ — a run that *measured* nothing, indistinguishable from a run
    that *found* nothing, which is the #88 class this tool exists to prevent.
    """
    if named is not None:
        return [_named_file_notice(named, project_dir, config)]
    return [NO_FILES_NOTICE if config.files is None else NOTHING_MATCHED_NOTICE]


def submodule_notices(placed: list[str], config: Config, project_dir: Path) -> list[str]:
    """One line per submodule this run would have measured inside, had it looked.

    Git names a submodule by its own directory and never by the files inside it,
    so a vendored subtree drops out of a scan. That is the right answer — every
    git-derived mode was always blind to one, and the submodule gates itself in
    its own repository — but a scope that quietly shrinks and then renders ✅ is
    the false clean this whole tool exists to stop. The partial case is the
    dangerous one: a project with its own ``src/`` goes on reporting about the
    rest and says nothing at all about what it skipped.

    **This module owns the whole decision**, both halves of it, because a notice
    that is right about one half and wrong about the other is worse than none.
    ``git_listing`` answers what a submodule *is* and ``scope`` owns the
    narrowing, so splitting the judgement between them would leave neither able
    to state the thing being claimed: that this run lost source it wanted.

    ``placed`` is what keeps a git-derived mode quiet about a submodule its own
    commits never touched: ``--last 1`` picks the paths that changed, and a
    submodule absent from them is not something that run left out. Without it
    every scoped run would announce every submodule the project has.
    """
    if not config.files:
        return []  # opting out of discovery is answered before any git call
    picked = set(placed)
    return [
        f"habit-sensors: {path} is a submodule; its files are scanned in "
        "their own repository"
        for path in git_listing.submodule_paths(project_dir)
        if path in picked and _held_source_this_run_wanted(path, config, project_dir)
    ]


def _held_source_this_run_wanted(
    submodule: str, config: Config, project_dir: Path
) -> bool:
    """Whether ``[files]`` would have kept anything the submodule holds.

    A project whose ``[files]`` already excludes the directory lost nothing by
    it being skipped, and telling it otherwise states something false about its
    own scan. The typescript plugin's ``!**/node_modules/**`` is the case: the
    scan is exactly the size that project expects, so there is nothing to say.

    Asked by listing what the submodule really holds rather than by matching its
    directory name, because a source glob (``**/*.py``) never matches a bare
    directory — so testing the name would silence every notice there is.
    """
    held = git_listing.project_files(project_dir / submodule)
    return bool(matching([f"{submodule}/{path}" for path in held], config.files or []))


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
