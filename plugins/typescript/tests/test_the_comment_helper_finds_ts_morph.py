"""Where the comment helper looks for ts-morph, and what it says when it is absent.

Node resolves a bare ``require`` from the requiring **file** upwards, so the
helper was asking the tree habit-hooks is installed into — for a consumer, a
Python site-packages tree with no ``node_modules`` anywhere above it. Every
install that puts the package outside the project (``pip``, ``uv tool``,
Homebrew) therefore died on the helper's first line, while this repository and
the vendoring routes passed by luck of layout: something above the helper
happened to have ts-morph in it.

ts-morph comes from the project, as eslint and knip do, so it is resolved from
the project — the arrangement ``eslint.config.mjs`` already uses for its parser
and plugin.
"""

from __future__ import annotations

from pathlib import Path

from comment_project import (
    SOURCE_FILE,
    as_ts_morph_spells,
    installed_outside_the_project,
    project,
    project_without_ts_morph,
    reported_files,
    run,
)


def test_an_install_outside_the_project_still_finds_ts_morph(tmp_path: Path) -> None:
    """The consumer's own ts-morph answers for a helper that ships elsewhere."""
    consumer = project(tmp_path)

    result = run(consumer, installed_outside_the_project(tmp_path))

    assert reported_files(result) == [as_ts_morph_spells(consumer / SOURCE_FILE)]


def test_a_project_without_ts_morph_is_told_to_install_it(tmp_path: Path) -> None:
    """A missing dependency is a first-contact mistake, so it answers in one line
    naming what to install — never the module loader's stack trace."""
    consumer = project_without_ts_morph(tmp_path)

    result = run(consumer, installed_outside_the_project(tmp_path))

    assert result.returncode != 0
    assert result.stderr.splitlines() == [
        "ts-morph is not installed in this project — npm install --save-dev ts-morph"
    ]
