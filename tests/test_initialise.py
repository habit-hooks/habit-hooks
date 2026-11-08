
from __future__ import annotations

from pathlib import Path

from git_repo import holding, tracking
from habit_hooks.initialise import plan
from plugin_fixture import write_plugin, write_project_config


def test_a_project_of_no_known_language_plans_the_generic_plugin_alone(
    init_project: Path,
) -> None:
    planned = plan(init_project)

    assert planned.languages == ()
    assert planned.plugins == ("generic",)


def test_a_project_of_no_known_language_asks_for_a_plugin_of_its_own(
    init_project: Path,
) -> None:
    assert plan(init_project).needs_a_new_plugin


def test_a_project_running_a_plugin_of_its_own_is_asked_for_no_other(
    init_project: Path,
) -> None:
    write_plugin(init_project, "cobol", {"config.toml": ""})
    write_project_config(init_project, 'plugins = ["cobol", "generic"]')

    assert not plan(init_project).needs_a_new_plugin


def test_the_file_that_announces_a_language_plans_its_plugin(
    init_project: Path,
) -> None:
    (init_project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    planned = plan(init_project)

    assert planned.languages == ("python",)
    assert planned.plugins == ("python", "generic")
    assert not planned.needs_a_new_plugin


def test_every_language_found_is_planned_before_the_languageless_plugin(
    init_project: Path,
) -> None:
    (init_project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (init_project / "tsconfig.json").write_text("{}\n", encoding="utf-8")

    assert plan(init_project).plugins == ("python", "typescript", "generic")


def test_a_source_file_names_a_language_with_no_config_file_to_announce_it(
    init_project: Path,
) -> None:
    tracking(init_project, {"src/app.py": "x = 1\n"})

    assert plan(init_project).languages == ("python",)


def test_a_source_file_git_has_not_been_shown_yet_names_a_language(
    init_project: Path,
) -> None:
    holding(init_project, {"src/app.py": "x = 1\n"})

    assert plan(init_project).languages == ("python",)


def test_a_file_git_ignores_names_no_language(init_project: Path) -> None:
    tracking(init_project, {".gitignore": "node_modules/\n"})
    vendored = init_project / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "index.d.ts").write_text("", encoding="utf-8")

    assert plan(init_project).languages == ()


def test_outside_a_repository_a_source_file_names_nothing(
    init_project: Path,
) -> None:
    (init_project / "src").mkdir()
    (init_project / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")

    assert plan(init_project).languages == ()


def test_a_project_with_no_config_is_not_configured_yet(
    init_project: Path,
) -> None:
    assert not plan(init_project).already_configured


def test_an_existing_config_decides_the_plugins_rather_than_the_detection(
    init_project: Path,
) -> None:
    (init_project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    write_project_config(init_project, 'plugins = ["generic"]')

    planned = plan(init_project)

    assert planned.already_configured
    assert planned.plugins == ("generic",)
    assert planned.languages == ("python",)


def test_a_config_that_names_no_plugins_plans_no_plugins(
    init_project: Path,
) -> None:
    (init_project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    write_project_config(init_project, "plugins = []")

    planned = plan(init_project)

    assert planned.already_configured
    assert planned.plugins == ()
    assert planned.languages == ("python",)
    assert planned.missing_tools == ()
