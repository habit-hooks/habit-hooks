from __future__ import annotations

from pathlib import Path

from git_repo import git
from habit_hooks.initialise import plan


def _tracking(project_dir: Path, files: dict[str, str]) -> None:
    git(project_dir, "init", "-q", "-b", "main", ".")
    for relative, body in files.items():
        path = project_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    git(project_dir, "add", "-A")


def test_a_php_file_inside_node_modules_names_no_language(init_project: Path) -> None:
    _tracking(
        init_project, {"node_modules/legacy-lib/index.php": "<?php echo 'legacy';\n"}
    )

    planned = plan(init_project)

    assert planned.languages == ()
    assert planned.plugins == ("generic",)


def test_a_typescript_file_in_a_nested_node_modules_names_no_language(
    init_project: Path,
) -> None:
    _tracking(
        init_project, {"packages/app/node_modules/x/index.ts": "export const x = 1;\n"}
    )

    assert plan(init_project).languages == ()


def test_a_python_file_inside_site_packages_names_no_language(
    init_project: Path,
) -> None:
    _tracking(init_project, {"site-packages/foo/mod.py": "x = 1\n"})

    assert plan(init_project).languages == ()


def test_a_php_file_inside_vendor_names_no_language(init_project: Path) -> None:
    _tracking(init_project, {"vendor/legacy/index.php": "<?php echo 'legacy';\n"})

    assert plan(init_project).languages == ()


def test_a_python_file_under_venv_names_no_language(init_project: Path) -> None:
    _tracking(init_project, {"venv/lib/python3.12/site-packages/dep.py": "x = 1\n"})

    assert plan(init_project).languages == ()


def test_a_python_file_under_dot_venv_names_no_language(init_project: Path) -> None:
    _tracking(init_project, {".venv/lib/dep.py": "x = 1\n"})

    assert plan(init_project).languages == ()


def test_real_php_source_still_names_php(init_project: Path) -> None:
    _tracking(init_project, {"src/app.php": "<?php echo 'app';\n"})

    assert plan(init_project).languages == ("php",)


def test_a_file_named_like_a_dependency_directory_still_names_its_language(
    init_project: Path,
) -> None:
    _tracking(init_project, {"src/vendorize.py": "x = 1\n"})

    assert plan(init_project).languages == ("python",)


def test_a_project_without_dependency_directories_is_unchanged(
    init_project: Path,
) -> None:
    _tracking(init_project, {"src/app.py": "x = 1\n", "README.md": "# demo\n"})

    assert plan(init_project).languages == ("python",)
