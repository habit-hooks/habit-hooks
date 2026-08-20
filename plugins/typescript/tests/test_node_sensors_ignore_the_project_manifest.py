"""The shipped Node helpers must run whatever the consumer's package.json says.

Node does not read a ``.js`` file to decide its module system: it walks up from
the script to the nearest ``package.json`` and reads ``"type"`` there. A
CommonJS helper named ``.js`` therefore dies on its first line —
``ReferenceError: require is not defined in ES module scope`` — in any project
declaring ``"type": "module"``, the default a new TypeScript project is
scaffolded with. Two of this plugin's three sensors were gone on the first run.

The helper is only inside the consumer's manifest scope when it sits under the
project directory, which is exactly what the two installs below do: the
vendoring route the README advertises (``.habit-hooks/<plugin>/sensors/``) and a
project-local ``.venv/``. ``.cjs`` settles the question inside the file, where
the consumer's manifest cannot reach it.

Every case copies the **shipped** helper byte for byte — a rewritten copy would
prove only that the rewrite works — and runs it under both manifests. The
CommonJS half is the control: same files, same project, one key removed, so a
failure under ``"type": "module"`` is the manifest's doing and nothing else.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSORS = PACKAGE / "sensors"

COMMENT_HELPER = "comment.cjs"
KNIP_HELPER = "knip.cjs"

ESM_MANIFEST = '{ "name": "demo", "version": "0.0.0", "type": "module" }\n'
COMMONJS_MANIFEST = '{ "name": "demo", "version": "0.0.0" }\n'

under_either_manifest = pytest.mark.parametrize(
    "manifest",
    [ESM_MANIFEST, COMMONJS_MANIFEST],
    ids=["esm", "commonjs"],
)


def _project(tmp_path: Path, manifest: str) -> Path:
    """A consumer project declaring `manifest`, with the plugin's Node tools."""
    project = tmp_path / "demo"
    (project / "src").mkdir(parents=True)
    (project / "package.json").write_text(manifest, encoding="utf-8")
    (project / "node_modules").symlink_to(PLUGIN / "node_modules")
    return project


def _vendored(project: Path, helper: str) -> Path:
    """The shipped helper, copied byte for byte to the README's vendoring path."""
    destination = project / ".habit-hooks" / "typescript" / "sensors" / helper
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SENSORS / helper, destination)
    return destination


def _installed_in_a_local_venv(project: Path, helper: str) -> Path:
    """The shipped helper, at the path `uv pip install` into `.venv/` uses."""
    destination = (
        project
        / ".venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "habit_hooks_typescript"
        / "sensors"
        / helper
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SENSORS / helper, destination)
    return destination


def _run(project: Path, helper: Path, *args: str) -> subprocess.CompletedProcess[str]:
    path = f"{project / 'node_modules' / '.bin'}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run(
        ["node", str(helper), *args],
        cwd=project,
        env={**os.environ, "PATH": path},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _with_a_non_essential_comment(project: Path) -> None:
    (project / "src" / "helper.ts").write_text(
        "export function used(): void {\n"
        "  // this comment restates what the code already says clearly\n"
        "}\n",
        encoding="utf-8",
    )


def _with_an_unused_export(project: Path) -> None:
    shutil.copy2(PACKAGE / "knip.json", project / "knip.json")
    (project / "src" / "cli.ts").write_text(
        'import { used } from "./helper";\n\nused();\n', encoding="utf-8"
    )
    (project / "src" / "helper.ts").write_text(
        "export function used(): void {}\n\nexport function neverUsed(): void {}\n",
        encoding="utf-8",
    )


def _findings(result: subprocess.CompletedProcess[str]) -> list[dict]:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _keys_of(findings: list[dict], smell: str) -> list[str]:
    return [
        issue["key"]
        for finding in findings
        if finding["smell"] == smell
        for issue in finding["issues"]
    ]


def _assert_reports_the_comment(findings: list[dict], project: Path) -> None:
    """The helper keys a comment by absolute path — the pipeline anchors it to
    the project later, at the sensor boundary, which is not what this is about."""
    reported = _keys_of(findings, "non-essential-comment")
    assert reported == [str((project / "src" / "helper.ts").resolve())], findings


@under_either_manifest
def test_vendored_comment_helper_reports_a_comment(tmp_path: Path, manifest: str) -> None:
    project = _project(tmp_path, manifest)
    _with_a_non_essential_comment(project)

    result = _run(project, _vendored(project, COMMENT_HELPER), "src/helper.ts")

    _assert_reports_the_comment(_findings(result), project)


@under_either_manifest
def test_vendored_knip_helper_reports_an_unused_export(tmp_path: Path, manifest: str) -> None:
    project = _project(tmp_path, manifest)
    _with_an_unused_export(project)

    result = _run(project, _vendored(project, KNIP_HELPER))

    findings = _findings(result)
    reported = [issue["key"] for finding in findings for issue in finding["issues"]]
    assert "neverUsed" in reported, findings


@under_either_manifest
def test_venv_installed_comment_helper_reports_a_comment(tmp_path: Path, manifest: str) -> None:
    """A project-local venv puts the helper under the consumer's manifest too."""
    project = _project(tmp_path, manifest)
    _with_a_non_essential_comment(project)

    helper = _installed_in_a_local_venv(project, COMMENT_HELPER)
    result = _run(project, helper, "src/helper.ts")

    _assert_reports_the_comment(_findings(result), project)
