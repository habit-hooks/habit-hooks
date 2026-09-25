
from __future__ import annotations

import shutil
import tempfile
import weakref
from pathlib import Path

import pytest

from harness import (
    POSIX_SHELL_ONLY,
    STEPS_RUN_ON_THIS_PLATFORM,
    Session,
    SpecCase,
    SpecError,
    SpecFailure,
    execute,
    parse_spec,
)

_REPO_ROOT = Path(__file__).parent


def _case_root() -> Path:
    root = _REPO_ROOT / ".spec-runs"
    root.mkdir(exist_ok=True)
    return root


def pytest_collect_file(parent, file_path):
    if file_path.name.endswith(".spec.md"):
        return SpecFile.from_parent(parent, path=file_path)


class SpecFile(pytest.File):
    def collect(self):
        root = Path(tempfile.mkdtemp(dir=_case_root()))
        weakref.finalize(self, shutil.rmtree, root, True)
        self.spec_session = Session(root)
        for case in parse_spec(self.path.read_text(encoding="utf-8")):
            yield SpecItem.from_parent(self, name=case.name, case=case)


class SpecItem(pytest.Item):
    def __init__(self, *, case: SpecCase, **kwargs):
        super().__init__(**kwargs)
        self.case = case

    def runtest(self):
        if not STEPS_RUN_ON_THIS_PLATFORM:
            pytest.skip(POSIX_SHELL_ONLY)
        if self.case.skip:
            pytest.skip("🟡 not built yet")
        workdir = self.parent.spec_session.workdir(self.case.continued)
        execute(self.case, workdir, _REPO_ROOT)

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, (SpecError, SpecFailure)):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return self.path, None, self.name
