"""habit-mapper: route findings to guides and set the exit code from severity."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

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
    # Look up ``<smell>.md`` for any smell — catalogued or not — so a custom
    # smell paired with a shipped guide is coached (render_finding falls back to
    # uncoached.md only when no plugin supplies one).
    extensions = ["md", *config.runners.keys()]
    return [f"{smell}.{ext}" for ext in extensions]


def plugins_for_language(language: str | None, config: Config) -> list[str]:
    """``config.plugins`` reordered to coach a finding of ``language``.

    Documented rule: take the first plugin whose declared language matches, in
    ``plugins`` order, then fall back to the languageless plugin (``generic``)
    last. A plugin that declares a *different* language does not coach the
    finding, so its guide is left out.
    """
    languages = config.plugin_languages
    matching = [
        p for p in config.plugins if language is not None and languages.get(p) == language
    ]
    fallback = [p for p in config.plugins if p not in languages]
    return matching + fallback


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


def _refuse_unconfigured_runner(smell: str, guide: Path, extension: str) -> NoReturn:
    raise SystemExit(
        f"habit-mapper: smell {smell!r} routes to guide {guide.name!r}, but the "
        f"{extension!r} extension has no [runners] command — add one or route to "
        f"a .md guide"
    )


def _resolve_guide(finding: dict, config: Config, resolver: Resolver) -> Path:
    plugins = plugins_for_language(finding.get("language"), config)
    guide = resolver.first(plugins, guide_names(finding["smell"], config))
    if guide is None:
        guide = resolver.guide(UNCOACHED_GUIDE, config.plugins)
    return guide


def _runner_for(config: Config, guide: Path, smell: str) -> str:
    """The configured runner command for a non-``.md`` guide, or refuse by name."""
    extension = guide.suffix.lstrip(".")
    runner = config.runners.get(extension)
    if runner is None:
        _refuse_unconfigured_runner(smell, guide, extension)
    return runner


def render_finding(finding: dict, config: Config, resolver: Resolver) -> Rendered:
    smell = finding["smell"]
    enforced = severity_of(smell, config) == ENFORCED
    guide = _resolve_guide(finding, config, resolver)
    if guide.suffix == ".md":
        environment = include_environment(config.plugins, resolver)
        rendered = render_markdown(guide, finding, environment)
    else:
        rendered = render_runner(guide, _runner_for(config, guide, smell), finding)
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


def run(
    findings: list[dict], project_dir: Path, config_path: Path | None = None
) -> int:
    config = load_config(project_dir, config_path)
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-mapper")
    parser.add_argument("--config", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(read_findings(), Path.cwd(), args.config)


if __name__ == "__main__":
    sys.exit(main())
