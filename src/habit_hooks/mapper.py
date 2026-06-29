"""habit-mapper: route findings to guides and set the exit code from severity."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

from .catalogue import DEFAULT_SEVERITY, ENFORCED, UNCOACHED_GUIDE
from .config import Config, load_config
from .resolve import resolve_first, resolve_guide

CLEAN_GUIDE = "clean.md"


@dataclass
class Rendered:
    text: str
    blocks: bool
    stderr: str = ""


def severity_of(smell: str, config: Config) -> str:
    override = config.smells.get(smell)
    if override and override.severity:
        return override.severity
    return DEFAULT_SEVERITY.get(smell, ENFORCED)


def guide_names(smell: str, config: Config) -> list[str]:
    override = config.smells.get(smell)
    if override and override.guide:
        return [override.guide]
    if smell not in DEFAULT_SEVERITY:
        return [UNCOACHED_GUIDE]
    extensions = ["md", *config.runners.keys()]
    return [f"{smell}.{ext}" for ext in extensions]


def render_markdown(guide: Path, finding: dict) -> Rendered:
    template = Template(guide.read_text())
    return Rendered(text=template.render(**finding), blocks=False)


def render_runner(guide: Path, runner: str, finding: dict, blocks: bool) -> Rendered:
    result = subprocess.run(
        [runner, str(guide)],
        input=json.dumps(finding),
        capture_output=True,
        text=True,
    )
    return Rendered(
        text=result.stdout,
        blocks=blocks and result.returncode != 0,
        stderr=result.stderr,
    )


def render_finding(
    finding: dict, config: Config, project_dir: Path, package_dir: Path
) -> Rendered:
    smell = finding["smell"]
    blocks = severity_of(smell, config) == ENFORCED
    guide = resolve_first(
        config.plugins, project_dir, package_dir, guide_names(smell, config)
    )
    if guide is None:
        raise SystemExit(f"no guide found for smell {smell!r}")
    extension = guide.suffix.lstrip(".")
    if extension == "md":
        rendered = render_markdown(guide, finding)
        rendered.blocks = blocks
        return rendered
    return render_runner(guide, config.runners[extension], finding, blocks)


def render_clean(config: Config, project_dir: Path, package_dir: Path) -> Rendered:
    guide = resolve_guide(CLEAN_GUIDE, config.plugins, project_dir, package_dir)
    return Rendered(text=guide.read_text(), blocks=False)


def run(findings: list[dict], project_dir: Path, package_dir: Path) -> int:
    config = load_config(project_dir)
    if not findings:
        clean = render_clean(config, project_dir, package_dir)
        sys.stdout.write(clean.text)
        return 0
    rendered = [render_finding(f, config, project_dir, package_dir) for f in findings]
    body = "\n\n".join(r.text.strip() for r in rendered if r.text.strip())
    if body:
        sys.stdout.write(body + "\n")
    for r in rendered:
        if r.stderr:
            sys.stderr.write(r.stderr)
    return 1 if any(r.blocks for r in rendered) else 0


def package_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "plugins").is_dir():
            return parent
    raise SystemExit("could not locate the package plugins directory")


def read_findings() -> list[dict]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else []


def main() -> int:
    return run(read_findings(), Path.cwd(), package_root())


if __name__ == "__main__":
    sys.exit(main())
