"""Every shipped sensor and transformer spells ``argv``.

``argv`` is spawned with no shell in between, and is the only form that runs on
native Windows — a ``command`` string is text for ``bash``, which Windows has
not got (and where ``bash`` resolves, it is usually the WSL launcher, answering
from another filesystem entirely). ``command`` stays in the contract for a
third-party plugin that needs syntax a list cannot carry, and is refused at run
time off POSIX; nothing this repo ships needs it any more. A new part added as
a ``command`` string would be dead on Windows without anything saying so — this
is the gate that notices.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.config_schema import read_toml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _shipped_part_specs() -> list[Path]:
    """Every sensor/transformer spec this repo ships, core and every plugin."""
    patterns = (
        "plugins/*/src/*/sensors/*.toml",
        "src/habit_hooks/sensors/*.toml",
        "src/habit_hooks/transformers/*.toml",
    )
    return sorted(path for pattern in patterns for path in REPO_ROOT.glob(pattern))


def test_every_shipped_part_spells_argv() -> None:
    specs = _shipped_part_specs()
    assert len(specs) == 11, specs  # a part added here must be judged too

    shell_recipes = [path for path in specs if "argv" not in read_toml(path)]

    assert shell_recipes == []
