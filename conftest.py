"""Collect the executable specs (``docs/**/*.spec.md``) as pytest tests.

Each leaf spec case (per ``docs/executable_spec.md``) becomes one pytest item,
so ``uv run pytest`` reports the specs alongside the harness's own unit tests
with native pass/skip/fail. The engine lives in ``tests/harness.py`` (importable
via the ``pythonpath`` set in ``pyproject.toml``).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from harness import SpecCase, SpecError, SpecFailure, execute, parse_spec

_REPO_ROOT = Path(__file__).parent


def _case_root() -> Path:
    """One level below the repo root, so a case dir created inside it sits two
    levels down and the specs' ``../../habit-mapper`` launcher shim resolves."""
    root = _REPO_ROOT / ".spec-runs"
    root.mkdir(exist_ok=True)
    return root


def pytest_collect_file(parent, file_path):
    if file_path.name.endswith(".spec.md"):
        return SpecFile.from_parent(parent, path=file_path)


class SpecFile(pytest.File):
    def collect(self):
        for case in parse_spec(self.path.read_text()):
            yield SpecItem.from_parent(self, name=case.name, case=case)


class SpecItem(pytest.Item):
    def __init__(self, *, case: SpecCase, **kwargs):
        super().__init__(**kwargs)
        self.case = case

    def runtest(self):
        if self.case.skip:
            pytest.skip("🟡 not built yet")
        with tempfile.TemporaryDirectory(dir=_case_root()) as tmp:
            execute(self.case, Path(tmp), _REPO_ROOT)

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, (SpecError, SpecFailure)):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return self.path, None, self.name
