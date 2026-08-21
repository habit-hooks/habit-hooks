"""Keep the paths a list of globs matches, gitignore-style.

One filter, asked by everything that narrows a path list: the run's ``[files]``
(``scope``), a single sensor's own ``files`` (``sensors/execution``), and the
question of whether a submodule held anything this run wanted (``scope_notices``).

It lives on its own so those three cannot come to disagree, and so the two that
are not ``scope`` need not import it — ``scope_notices`` is ``scope``'s own
dependency, and importing back would be a cycle.
"""

from __future__ import annotations

import pathspec


def matching(paths: list[str], globs: list[str]) -> list[str]:
    """The ``paths`` kept by pathspec (gitignore) ``globs``, order preserved.

    Gitignore semantics, so a later negation overrides an earlier match and
    there is no brace expansion. An empty ``globs`` keeps nothing, which is what
    makes discovery opt-in (#97) rather than accidentally universal.
    """
    spec = pathspec.PathSpec.from_lines("gitignore", globs)
    return [path for path in paths if spec.match_file(path)]
