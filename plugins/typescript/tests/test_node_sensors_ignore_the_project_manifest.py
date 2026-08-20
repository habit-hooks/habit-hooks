"""The shipped Node helpers must run whatever the consumer's package.json says.

Node does not read a ``.js`` file to decide its module system: it walks up from
the script to the nearest ``package.json`` and reads ``"type"`` there. A
CommonJS helper named ``.js`` therefore dies on its first line —
``ReferenceError: require is not defined in ES module scope`` — in any project
declaring ``"type": "module"``, the default a new TypeScript project is
scaffolded with. Two of this plugin's three sensors were gone on the first run.

The helper is only inside the consumer's manifest scope when it sits under the
project directory, which is exactly what the two layouts here do
(``plugin_layouts``): the vendoring route the README advertises
(``.habit-hooks/<plugin>/``) and a project-local ``.venv/``. ``.cjs`` settles the
question inside the file, where the consumer's manifest cannot reach it.

Every case runs the **shipped** helper, copied byte for byte, under both
manifests. The CommonJS half is the control: same files, same project, one key
removed, so a failure under ``"type": "module"`` is the manifest's doing and
nothing else.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from plugin_layouts import PACKAGE, in_a_local_venv, sensor, vendored

PLUGIN = Path(__file__).parents[1]

COMMENT_HELPER = "comment.cjs"
KNIP_HELPER = "knip.cjs"
ESLINT_HELPER = "eslint.cjs"

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


def _with_a_too_wide_signature(project: Path) -> None:
    """Four parameters, which the shipped config caps at three — so a finding
    here also proves the copy reached the config copied beside it."""
    (project / "src" / "helper.ts").write_text(
        "export function charge(a: number, b: number, c: number, d: number): number {\n"
        "  return a + b + c + d;\n"
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


def _keys_of(result: subprocess.CompletedProcess[str], smell: str) -> list[str]:
    assert result.returncode == 0, result.stderr
    return [
        issue["key"]
        for finding in json.loads(result.stdout)
        if finding["smell"] == smell
        for issue in finding["issues"]
    ]


def _the_helper_file(project: Path) -> list[str]:
    """How a helper keys the fixture's one source: by absolute path. The pipeline
    anchors it to the project later, at the sensor boundary, which is not what
    these cases are about."""
    return [str((project / "src" / "helper.ts").resolve())]


@under_either_manifest
def test_vendored_comment_helper_reports_a_comment(
    tmp_path: Path, manifest: str
) -> None:
    project = _project(tmp_path, manifest)
    _with_a_non_essential_comment(project)

    helper = sensor(vendored(project), COMMENT_HELPER)
    result = _run(project, helper, "src/helper.ts")

    assert _keys_of(result, "non-essential-comment") == _the_helper_file(project)


@under_either_manifest
def test_vendored_knip_helper_reports_an_unused_export(
    tmp_path: Path, manifest: str
) -> None:
    project = _project(tmp_path, manifest)
    _with_an_unused_export(project)

    result = _run(project, sensor(vendored(project), KNIP_HELPER))

    assert "neverUsed" in _keys_of(result, "unused-export"), result.stdout


@under_either_manifest
def test_vendored_eslint_helper_reports_a_smell(tmp_path: Path, manifest: str) -> None:
    project = _project(tmp_path, manifest)
    _with_a_too_wide_signature(project)

    helper = sensor(vendored(project), ESLINT_HELPER)
    result = _run(project, helper, "--", "src/helper.ts")

    assert _keys_of(result, "too-many-parameters") == _the_helper_file(project)


@under_either_manifest
def test_venv_installed_comment_helper_reports_a_comment(
    tmp_path: Path, manifest: str
) -> None:
    """A project-local venv puts the helper under the consumer's manifest too."""
    project = _project(tmp_path, manifest)
    _with_a_non_essential_comment(project)

    helper = sensor(in_a_local_venv(project), COMMENT_HELPER)
    result = _run(project, helper, "src/helper.ts")

    assert _keys_of(result, "non-essential-comment") == _the_helper_file(project)
