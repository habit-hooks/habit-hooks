"""Every file a project has: what git says it keeps, or what is on disk when git
is not the thing to ask.

A whole-project run used to walk the directory tree and measure whatever it
found, while every git-derived mode asked git and so had never seen a build
artifact in its life. One project, two universes (#142): a real pnpm monorepo
held 321 tracked ``.ts``/``.tsx`` files and 843 on disk — 181 in ``dist/``, 326
in a tool cache, 14 in ``.next/`` — and its owner had to hand-write
``!**/dist/**`` into ``[files]`` before a run was usable. A default somebody has
to patch is the wrong default, so the walk is now the fallback and git's list is
the answer.

What a run then makes of that list — the ``[files]`` narrowing, dropping paths
the work tree no longer has, the opt-in that stops any of it happening at all —
is ``scope.py``, which is this module's only caller. The dependency runs one
way, and on through ``git_listing`` to ``git_command``: what a project holds is
a smaller question than what a run measures.
"""

from __future__ import annotations

from pathlib import Path

from . import git_listing


def files_in(project_dir: Path) -> list[str]:
    """The project's own files, sorted — git's account of them where there is one.

    Git saying nothing is never read as "nothing to scan". Outside a repository,
    on a machine with no git, and on any failure at all, git's answer is empty
    and the disk answers instead: a run that over-scans is a nuisance, where one
    that silently scans nothing reports a whole tree clean without reading it.
    """
    return sorted(_files_git_keeps(project_dir) or _files_on_disk(project_dir))


def _files_git_keeps(project_dir: Path) -> list[str]:
    """What git tracks here, plus what was just written and is not ignored — or
    nothing, when this project is the wrong thing to ask git about.

    Untracked-but-not-ignored has to be in it: the file just written is the one
    most likely to carry a fresh smell, and narrowing to the index alone would
    be a worse bug than the one this fixes.

    A project that is *itself* ignored by the repository around it has every file
    in it ignored, by a rule that was never about this project — a checkout
    vendored into somebody's ``vendor/``, or one of this repository's own spec
    cases under the ``.spec-runs/`` its ``.gitignore`` covers. Trusting git there
    would scope the run to nothing and call the lot clean, so the directory is
    asked about first and the list given up rather than believed.

    A submodule comes back as its own directory and never the files inside it,
    so a submodule's source leaves the scope. That is what every git-derived mode
    already does with it — ``git diff`` does not descend into a submodule either
    — and it is another repository, which gates itself.
    """
    if git_listing.ignores_directory(project_dir):
        return []
    return git_listing.project_files(project_dir)


def _files_on_disk(project_dir: Path) -> list[str]:
    """Every file under the project, whatever any repository makes of it.

    ``as_posix`` rather than ``str``: git names a nested file ``src/a.py`` on
    every platform, and this branch builds its own strings out of ``os.sep`` —
    a backslash on Windows.

    The payoff is the **sort** in :func:`files_in`, which orders whatever these
    two branches produce. ``\\`` and ``/`` sort differently, so on Windows the
    same project would come back in one order from git and another from the
    walk. No caller ever sees the backslash itself — ``scope._placed`` puts
    every path through ``project_paths.project_relative``, which normalises
    again — so this is about the two branches being interchangeable, not about
    a spelling escaping into a finding.
    """
    return [
        path.relative_to(project_dir).as_posix()
        for path in project_dir.rglob("*")
        if path.is_file()
    ]
