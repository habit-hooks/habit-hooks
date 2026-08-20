"""Run the jscpd CLI and print ``duplicated-code`` findings.

jscpd writes its result to a report file rather than stdout, and exits non-zero
when duplication crosses its configured threshold. This wrapper runs it against a
temp report, reads that report regardless of the exit code, and shapes each clone
into a finding.

The config it runs under is the project's whenever the project has one: the
plugin's bundled ``.jscpd.json`` arrives as ``--fallback-config`` and is reached
for only when jscpd's own discovery would come up empty.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tool_spawn import run_tool

JSCPD_CONFIG = ".jscpd.json"
PACKAGE_JSON = "package.json"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback-config", required=True)
    return parser.parse_args(argv)


def manifest_of(project: Path) -> dict:
    """``package.json``'s contents, or nothing — unreadable counts as absent.

    jscpd warns about a manifest it cannot parse and carries on with its other
    sources. Raising here instead would let a typo in a file this sensor only
    peeks at turn every run into a run that never completed.
    """
    manifest = project / PACKAGE_JSON
    if not manifest.is_file():
        return {}
    try:
        content = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return content if isinstance(content, dict) else {}


def project_configures_jscpd(project: Path) -> bool:
    """Whether jscpd's own discovery finds a config of the project's in ``project``.

    jscpd reads exactly two places, both relative to the directory it runs in:
    ``.jscpd.json``, then a ``jscpd`` key in ``package.json`` (``prepareOptions``
    in jscpd 4's ``init/options``). Answering from any wider set would tell a
    project its config was honoured where jscpd would never have read it.
    """
    if (project / JSCPD_CONFIG).is_file():
        return True
    return bool(manifest_of(project).get("jscpd"))


def scan_paths(config: str) -> list[str]:
    return json.loads(Path(config).read_text(encoding="utf-8"))["path"]


def config_arguments(fallback: str, project: Path) -> list[str]:
    """The config and scan paths to hand jscpd, given whose config is in play.

    A project that configures jscpd itself is handed nothing: jscpd's own
    discovery reads that config, and resolves its relative ``path`` entries
    against the project, because that is where the config sits.

    Ours is named only when the project has none — and then its ``path`` has to
    travel as positional arguments, because jscpd resolves a config's relative
    ``path`` against the *config file's* directory, and ours sits inside the
    installed package where ``src`` names nothing the project owns.
    """
    if project_configures_jscpd(project):
        return []
    return ["--config", fallback, *scan_paths(fallback)]


def run_jscpd(arguments: list[str], output: Path) -> subprocess.CompletedProcess[str]:
    """What jscpd said, or what a shell says about a jscpd nobody installed.

    This wrapper is what looks for jscpd — ``tool_spawn`` turns its name into
    the file this project runs for it, which is the only spelling Windows can
    spawn a ``jscpd.CMD`` shim by. An absent tool raised a ``FileNotFoundError``
    out of here and twenty lines of Python internals became the sensor's
    diagnosis (#114), so it answers the way the shell would have instead — and
    that phrase is what the run recognises to name the missing tool.
    """
    command = ["jscpd", "--reporters", "json", "--output", str(output)]
    try:
        return run_tool([*command, *arguments])
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "jscpd: command not found\n")


def occurrence(side: dict) -> dict:
    return {
        "key": side["name"],
        "details": {
            "file": side["name"],
            "startLine": side["start"],
            "endLine": side["end"],
            "source": "jscpd:duplication",
        },
    }


def clone_finding(clone: dict) -> dict:
    return {
        "smell": "duplicated-code",
        "details": {"lines": clone["lines"], "tokens": clone["tokens"]},
        "issues": [occurrence(clone["firstFile"]), occurrence(clone["secondFile"])],
    }


def findings(report: Path) -> list[dict]:
    if not report.is_file():
        return []
    clones = json.loads(report.read_text(encoding="utf-8"))["duplicates"]
    return [clone_finding(clone) for clone in clones]


def main(argv: list[str] | None = None) -> int:
    """Print the findings, or fail the way the tool did.

    Neither signal jscpd gives is conclusive alone, so both are read:

    - **exit 0, no report** — it scanned and found no clones. jscpd only writes a
      report when it has duplicates to put in it, so this is the ordinary clean
      case and must stay clean.
    - **exit 0, report** — clones under the configured threshold.
    - **non-zero, report** — duplication crossed the threshold. A real result;
      the report is read regardless of the exit code.
    - **non-zero, no report** — jscpd itself broke. Saying ``[]`` here would be
      this wrapper promising a clean run on behalf of a tool that never
      delivered one, so its complaint is forwarded and the sensor fails.
    """
    args = parse_args(argv if argv is not None else sys.argv[1:])
    arguments = config_arguments(args.fallback_config, Path.cwd())
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        result = run_jscpd(arguments, output)
        report = output / "jscpd-report.json"
        if result.returncode != 0 and not report.is_file():
            sys.stderr.write(result.stderr or result.stdout)
            return 1
        print(json.dumps(findings(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
