
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(project_dir: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project_dir, check=True, capture_output=True)


def stop_the_upward_walk_at(directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(directory))


def repository(project_dir: Path, ignoring: str = "") -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    git(project_dir, "init", "-q", "-b", "main", ".")
    git(project_dir, "config", "user.email", "spec@example.com")
    git(project_dir, "config", "user.name", "Spec Runner")
    git(project_dir, "config", "commit.gpgsign", "false")
    if ignoring:
        (project_dir / ".gitignore").write_text(ignoring, encoding="utf-8")
    return project_dir


def repository_with_committed_file(project_dir: Path) -> Path:
    committed_file = project_dir / "src.py"
    committed_file.write_text("VALUES = [1]\n", encoding="utf-8")
    repository(project_dir)
    git(project_dir, "add", "src.py")
    git(project_dir, "commit", "-q", "-m", "baseline")
    return committed_file


def holding(project_dir: Path, files: dict[str, str]) -> None:
    git(project_dir, "init", "-q", "-b", "main", ".")
    for relative, body in files.items():
        path = project_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def tracking(project_dir: Path, files: dict[str, str]) -> None:
    holding(project_dir, files)
    git(project_dir, "add", "-A")


def written(file: Path) -> Path:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("x = 1\n", encoding="utf-8")
    return file


def committed(project_dir: Path, file: Path) -> Path:
    written(file)
    git(project_dir, "add", "--force", str(file.relative_to(project_dir)))
    git(project_dir, "commit", "-q", "-m", f"add {file.name}")
    return file


def submodule(project_dir: Path, inner: Path, at: str) -> Path:
    git(
        project_dir,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "--quiet",
        "add",
        inner.as_posix(),
        at,
    )
    git(project_dir, "commit", "-q", "-m", f"vendor {at}")
    return project_dir / at


def tracked_symlink(project_dir: Path, at: str, target: Path) -> Path:
    link = project_dir / at
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    git(project_dir, "add", at)
    git(project_dir, "commit", "-q", "-m", f"link {at}")
    return link


def commit_file(file: Path, body: str) -> None:
    file.write_text(body, encoding="utf-8")
    git(file.parent, "add", file.name)
    git(file.parent, "commit", "-q", "-m", f"change {file.name}")
