"""Running the shipped comment helper over a throwaway consumer project.

The scaffolding ``test_the_comment_helper_finds_ts_morph`` drives, kept beside
``eslint_project`` and ``knip_project`` for the same reason they exist: where the
helper is installed and what the project has in it are the whole subject, so each
case has to lay both out for real rather than stub them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSORS = PACKAGE / "sensors"
HELPER = SENSORS / "comment.cjs"

COMMONJS_MANIFEST = '{ "name": "demo", "version": "0.0.0" }\n'

SOURCE_WITH_A_COMMENT = (
    "export function used(): void {\n"
    "  // this comment restates what the code already says clearly\n"
    "}\n"
)
SOURCE_FILE = "src/helper.ts"


def project(tmp_path: Path, manifest: str = COMMONJS_MANIFEST) -> Path:
    """A consumer project declaring `manifest`, with the plugin's Node tools."""
    created = _bare_project(tmp_path, manifest)
    (created / "node_modules").symlink_to(PLUGIN / "node_modules")
    return created


def project_without_ts_morph(tmp_path: Path) -> Path:
    """The same project before anyone ran `npm install` — no node_modules at all."""
    return _bare_project(tmp_path, COMMONJS_MANIFEST)


def _bare_project(tmp_path: Path, manifest: str) -> Path:
    created = tmp_path / "demo"
    (created / "src").mkdir(parents=True)
    (created / "package.json").write_text(manifest, encoding="utf-8")
    (created / SOURCE_FILE).write_text(SOURCE_WITH_A_COMMENT, encoding="utf-8")
    return created


def installed_outside_the_project(tmp_path: Path) -> Path:
    """The shipped helper where `pip`, `uv tool` and Homebrew put it: a
    site-packages tree of its own, with no `node_modules` anywhere above it."""
    return _copied_to(
        tmp_path / "site-packages" / "habit_hooks_typescript" / "sensors" / HELPER.name
    )


def _copied_to(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HELPER, destination)
    return destination


def run(project: Path, helper: Path) -> subprocess.CompletedProcess[str]:
    """What the helper does about the project's one file, as the runner spawns it
    (`sensors/spawn.py` puts the project's tool bins on PATH)."""
    path = f"{project / 'node_modules' / '.bin'}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run(
        ["node", str(helper), SOURCE_FILE],
        cwd=project,
        env={**os.environ, "PATH": path},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def reported_files(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The keys of every comment the helper reported."""
    assert result.returncode == 0, result.stderr
    return [
        issue["key"]
        for finding in json.loads(result.stdout)
        for issue in finding["issues"]
    ]
