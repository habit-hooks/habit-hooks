"""habit-mapper: route findings to guides and set the exit code from severity.

Rendering one finding into text lives in :mod:`habit_hooks.rendering`; this
module is the stage around it — what arrives on stdin, what reaches stdout, and
which exit code says so.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalogue import incomplete_run_finding
from .cli import EXIT_TOOL_ERROR, add_version_flag, run_console
from .config import Config, load_config
from .merged_findings import merged
from .rendering import (
    Rendered,
    block,
    is_disabled,
    render_clean,
    render_finding,
    resolve_guide,
)
from .resolve import Resolver

EMPTY_STDIN_NOTICE = (
    "habit-mapper: nothing arrived on stdin — the sensors stage exited before it "
    "wrote any findings"
)


def write_stderr(rendered: list[Rendered]) -> None:
    for r in rendered:
        if r.stderr:
            sys.stderr.write(r.stderr)


def coachable(findings: list[dict], config: Config, resolver: Resolver) -> list[dict]:
    """The findings this run prints: what the project coaches, one per guide.

    Two sensors seeing one smell are one finding by the time anything renders
    (:mod:`habit_hooks.merged_findings`), and which guide each would render is
    what decides who merges with whom.
    """
    coached = [f for f in findings if not is_disabled(f["smell"], config)]
    return merged(coached, lambda f: resolve_guide(f, config, resolver))


def run(
    findings: list[dict], project_dir: Path, config_path: Path | None = None
) -> int:
    config = load_config(project_dir, config_path)
    resolver = Resolver.discover(project_dir)
    findings = coachable(findings, config, resolver)
    if not findings:
        clean = render_clean(config, resolver)
        sys.stdout.write(clean.text)
        return 0
    rendered = [render_finding(f, config, resolver) for f in findings]
    blocks = [
        block(f, r.text) for f, r in zip(findings, rendered) if r.text.strip()
    ]
    body = "\n\n".join(blocks)
    if body:
        sys.stdout.write(body + "\n")
    write_stderr(rendered)
    return 1 if any(r.blocks for r in rendered) else 0


def read_findings() -> list[dict] | None:
    """The findings array, or ``None`` when the stream is wholly empty.

    A stage that completes always writes at least ``[]``, so zero bytes can only
    mean it died before writing — the one failure #88's reserved finding cannot
    travel through, because nothing travels at all.
    """
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else None


def coach_incomplete_run(project_dir: Path, config_path: Path | None) -> int:
    """Coach the empty pipe as an incomplete run, and exit as a tool failure.

    Rendered directly rather than through :func:`run`, because a project's
    ``[smells.incomplete-run] disabled`` speaks about code smells and must not
    turn a scan that never ran into a clean one.
    """
    config = load_config(project_dir, config_path)
    resolver = Resolver.discover(project_dir)
    finding = incomplete_run_finding([EMPTY_STDIN_NOTICE])
    rendered = render_finding(finding, config, resolver)
    # The exit code is fixed at 2 here, so a runner-backed override of
    # incomplete-run.md contributes its stdout only: its `blocks` cannot lower
    # the code and its stderr is dropped.
    sys.stdout.write(block(finding, rendered.text) + "\n")
    return EXIT_TOOL_ERROR


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-mapper")
    add_version_flag(parser)
    parser.add_argument("--config", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run_console("habit-mapper", _render_findings, argv)


def _render_findings(argv: list[str]) -> int:
    args = parse_args(argv)
    findings = read_findings()
    if findings is None:
        return coach_incomplete_run(Path.cwd(), args.config)
    return run(findings, Path.cwd(), args.config)


if __name__ == "__main__":
    sys.exit(main())
