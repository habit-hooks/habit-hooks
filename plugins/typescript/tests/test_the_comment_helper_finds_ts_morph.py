
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
    consumer = project(tmp_path)

    result = run(consumer, installed_outside_the_project(tmp_path))

    assert reported_files(result) == [as_ts_morph_spells(consumer / SOURCE_FILE)]


def test_short_comments_are_still_reported(tmp_path: Path) -> None:
    consumer = project(tmp_path)
    (consumer / SOURCE_FILE).write_text(
        "// note\n"
        "/* why */\n"
        "export const other = 2;\n",
        encoding="utf-8",
    )

    result = run(consumer, installed_outside_the_project(tmp_path))

    assert reported_files(result) == [
        as_ts_morph_spells(consumer / SOURCE_FILE),
        as_ts_morph_spells(consumer / SOURCE_FILE),
    ]


def test_a_project_without_ts_morph_is_told_to_install_it(tmp_path: Path) -> None:
    consumer = project_without_ts_morph(tmp_path)

    result = run(consumer, installed_outside_the_project(tmp_path))

    assert result.returncode != 0
    assert result.stderr.splitlines() == [
        "ts-morph is not installed in this project — npm install --save-dev ts-morph"
    ]
