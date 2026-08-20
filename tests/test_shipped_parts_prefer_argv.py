"""Every shipped sensor and transformer spells ``argv`` unless it genuinely
needs a shell.

``argv`` is spawned with no shell in between and is the only form that runs on
native Windows; ``command`` buys shell syntax a list cannot carry — a pipe into
``jq``, ``set -o pipefail`` — at the price of needing ``bash``. Of the eleven
parts this repo ships, only ``ruff`` and ``eslint`` pipe their tool through
``jq`` and so are the only two that still need it. A new part shipped as a
``command`` string, needing no such syntax, would silently regress the
Windows story this repo is building — this is the gate that notices.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.config_schema import read_toml

REPO_ROOT = Path(__file__).resolve().parents[1]

# (directory relative to REPO_ROOT, part name) for every shipped part that
# genuinely needs a shell, and why: both pipe their tool's output into ``jq``.
SHELL_IS_LOAD_BEARING = {
    ("plugins/python/src/habit_hooks_python/sensors", "ruff"),
    ("plugins/typescript/src/habit_hooks_typescript/sensors", "eslint"),
}


def _shipped_part_specs() -> list[Path]:
    """Every sensor/transformer spec this repo ships, core and every plugin."""
    patterns = (
        "plugins/*/src/*/sensors/*.toml",
        "src/habit_hooks/sensors/*.toml",
        "src/habit_hooks/transformers/*.toml",
    )
    return sorted(path for pattern in patterns for path in REPO_ROOT.glob(pattern))


def test_every_shipped_part_that_can_spell_argv_does() -> None:
    specs = _shipped_part_specs()
    assert len(specs) == 11, specs  # a part added here must be judged too

    offenders = []
    for spec_path in specs:
        spec = read_toml(spec_path)
        if "argv" in spec:
            continue
        location = (
            spec_path.parent.relative_to(REPO_ROOT).as_posix(),
            spec_path.stem,
        )
        if location in SHELL_IS_LOAD_BEARING:
            continue
        offenders.append(spec_path)

    assert offenders == []


def test_every_shell_exemption_still_needs_a_shell() -> None:
    """The allowlist itself must stay honest: an exempted part that no longer
    pipes through ``jq`` should be moved back onto ``argv``, not left here."""
    for directory, name in SHELL_IS_LOAD_BEARING:
        spec = read_toml(REPO_ROOT / directory / f"{name}.toml")
        assert "argv" not in spec, (directory, name)
        assert "| jq" in spec["command"], (directory, name)
