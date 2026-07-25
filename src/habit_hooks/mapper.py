"""habit-mapper: route findings to guides and set the exit code from severity."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FunctionLoader

from .catalogue import DEFAULT_SEVERITY, ENFORCED, UNCOACHED_GUIDE
from .config import Config, load_config
from .resolve import Resolver

CLEAN_GUIDE = "clean.md"


@dataclass
class Rendered:
    text: str
    blocks: bool
    stderr: str = ""


def is_disabled(smell: str, config: Config) -> bool:
    override = config.smells.get(smell)
    return bool(override and override.disabled)


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


def include_environment(plugins: list[str], resolver: Resolver) -> Environment:
    def load(name: str) -> str | None:
        partial = resolver.first(plugins, [name])
        return None if partial is None else partial.read_text()

    return Environment(loader=FunctionLoader(load))


def render_markdown(guide: Path, finding: dict, environment: Environment) -> Rendered:
    template = environment.from_string(guide.read_text())
    return Rendered(text=template.render(**finding), blocks=True)


def render_runner(guide: Path, runner: str, finding: dict) -> Rendered:
    result = subprocess.run(
        [runner, str(guide)],
        input=json.dumps(finding),
        capture_output=True,
        text=True,
    )
    return Rendered(
        text=result.stdout,
        blocks=result.returncode != 0,
        stderr=result.stderr,
    )


def render_finding(finding: dict, config: Config, resolver: Resolver) -> Rendered:
    smell = finding["smell"]
    enforced = severity_of(smell, config) == ENFORCED
    guide = resolver.first(config.plugins, guide_names(smell, config))
    if guide is None:
        guide = resolver.guide(UNCOACHED_GUIDE, config.plugins)
    extension = guide.suffix.lstrip(".")
    if extension == "md":
        environment = include_environment(config.plugins, resolver)
        rendered = render_markdown(guide, finding, environment)
    else:
        rendered = render_runner(guide, config.runners[extension], finding)
    rendered.blocks = enforced and rendered.blocks
    return rendered


def render_clean(config: Config, resolver: Resolver) -> Rendered:
    guide = resolver.guide(CLEAN_GUIDE, config.plugins)
    return Rendered(text=guide.read_text(), blocks=False)


def write_stderr(rendered: list[Rendered]) -> None:
    for r in rendered:
        if r.stderr:
            sys.stderr.write(r.stderr)


def banner(finding: dict) -> str:
    count = len(finding["issues"])
    noun = "issue" if count == 1 else "issues"
    return f"── {finding['smell']} ({count} {noun}) ──"


def run(findings: list[dict], project_dir: Path) -> int:
    config = load_config(project_dir)
    resolver = Resolver.discover(project_dir)
    findings = [f for f in findings if not is_disabled(f["smell"], config)]
    if not findings:
        clean = render_clean(config, resolver)
        sys.stdout.write(clean.text)
        return 0
    rendered = [render_finding(f, config, resolver) for f in findings]
    blocks = [
        f"{banner(f)}\n\n{r.text.strip()}"
        for f, r in zip(findings, rendered)
        if r.text.strip()
    ]
    body = "\n\n".join(blocks)
    if body:
        sys.stdout.write(body + "\n")
    write_stderr(rendered)
    return 1 if any(r.blocks for r in rendered) else 0


def read_findings() -> list[dict]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else []


def main() -> int:
    return run(read_findings(), Path.cwd())


if __name__ == "__main__":
    sys.exit(main())
