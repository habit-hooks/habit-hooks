"""Unit tests for what ``habit-hooks init`` plans for a project.

Installing the tool is its most frequent support question, so the plan has to be
right about three things before a word is printed: which languages the project
is written in, which plugins that asks for, and whether the project is already
configured — in which case a re-run reports and changes nothing.

What then stands in the way of running it has a file per kind: the plugins
nobody has are ``test_uninstalled_plugins.py``, and the tools they reach for
``test_missing_tools.py``.
"""

from __future__ import annotations

from pathlib import Path

from git_repo import git
from habit_hooks.initialise import plan
from plugin_fixture import write_plugin, write_project_config


def _holding(project_dir: Path, files: dict[str, str]) -> None:
    """A repository holding ``files``, written where they name and left untracked."""
    git(project_dir, "init", "-q", "-b", "main", ".")
    for relative, body in files.items():
        path = project_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def _tracking(project_dir: Path, files: dict[str, str]) -> None:
    """The same, with everything in it added to the index."""
    _holding(project_dir, files)
    git(project_dir, "add", "-A")


def test_a_project_of_no_known_language_plans_the_generic_plugin_alone(
    init_project: Path,
) -> None:
    """``generic`` speaks no language, so it is what every project gets."""
    planned = plan(init_project)

    assert planned.languages == ()
    assert planned.plugins == ("generic",)


def test_a_project_of_no_known_language_asks_for_a_plugin_of_its_own(
    init_project: Path,
) -> None:
    """There is nothing here to install, so the offer is a plugin to *write* —
    and only the plan can tell that case from a language it recognised."""
    assert plan(init_project).needs_a_new_plugin


def test_a_project_running_a_plugin_of_its_own_is_asked_for_no_other(
    init_project: Path,
) -> None:
    """Habit-hooks recognises none of this project's languages and never will —
    somebody wrote the plugin for it. Telling them to go and write one is the
    advice their own config is the answer to."""
    write_plugin(init_project, "cobol", {"config.toml": ""})
    write_project_config(init_project, 'plugins = ["cobol", "generic"]')

    assert not plan(init_project).needs_a_new_plugin


def test_the_file_that_announces_a_language_plans_its_plugin(
    init_project: Path,
) -> None:
    (init_project / "pyproject.toml").write_text("[project]\n")

    planned = plan(init_project)

    assert planned.languages == ("python",)
    assert planned.plugins == ("python", "generic")
    assert not planned.needs_a_new_plugin


def test_every_language_found_is_planned_before_the_languageless_plugin(
    init_project: Path,
) -> None:
    """``plugins`` order is a priority — the mapper prefers a plugin that speaks
    the finding's language over the fallback — so ``generic`` goes last."""
    (init_project / "pyproject.toml").write_text("[project]\n")
    (init_project / "tsconfig.json").write_text("{}\n")

    assert plan(init_project).plugins == ("python", "typescript", "generic")


def test_a_source_file_names_a_language_with_no_config_file_to_announce_it(
    init_project: Path,
) -> None:
    """A Python tree older than ``pyproject.toml`` is still Python."""
    _tracking(init_project, {"src/app.py": "x = 1\n"})

    assert plan(init_project).languages == ("python",)


def test_a_source_file_git_has_not_been_shown_yet_names_a_language(
    init_project: Path,
) -> None:
    """`git init` and then set the tool up is the ordinary first ten minutes, so
    a repository with nothing added to it yet is the commonest one init sees."""
    _holding(init_project, {"src/app.py": "x = 1\n"})

    assert plan(init_project).languages == ("python",)


def test_a_file_git_ignores_names_no_language(init_project: Path) -> None:
    """``node_modules`` ships ``.d.ts`` by the thousand, so a Python repository
    with a lint toolchain installed would be planned as TypeScript — and its
    first run would then fail on tools nobody asked for."""
    _tracking(init_project, {".gitignore": "node_modules/\n"})
    vendored = init_project / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "index.d.ts").write_text("")

    assert plan(init_project).languages == ()


def test_outside_a_repository_a_source_file_names_nothing(
    init_project: Path,
) -> None:
    """Git's list is what says which files are the project's own; without one,
    walking the directory is how ``node_modules`` gets read as its TypeScript.
    The file that announces a language still answers."""
    (init_project / "src").mkdir()
    (init_project / "src" / "app.py").write_text("x = 1\n")

    assert plan(init_project).languages == ()


def test_a_project_with_no_config_is_not_configured_yet(
    init_project: Path,
) -> None:
    assert not plan(init_project).already_configured


def test_an_existing_config_decides_the_plugins_rather_than_the_detection(
    init_project: Path,
) -> None:
    """A re-run changes nothing, so what it reports on is the run this project
    actually gets — while still naming the language it found, which is the
    project's own to act on."""
    (init_project / "pyproject.toml").write_text("[project]\n")
    write_project_config(init_project, 'plugins = ["generic"]')

    planned = plan(init_project)

    assert planned.already_configured
    assert planned.plugins == ("generic",)
    assert planned.languages == ("python",)


def test_a_config_that_names_no_plugins_plans_no_plugins(
    init_project: Path,
) -> None:
    """Every plugin switched off is a run that reports nothing, and a re-run
    says so — the answer to "why is this run not reporting anything?" — rather
    than planning the plugins the project would otherwise have got."""
    (init_project / "pyproject.toml").write_text("[project]\n")
    write_project_config(init_project, "plugins = []")

    planned = plan(init_project)

    assert planned.already_configured
    assert planned.plugins == ()
    assert planned.languages == ("python",)
    assert planned.missing_tools == ()
