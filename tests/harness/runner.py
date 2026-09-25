from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .errors import SpecError
from .parser import SpecCase
from .steps import Context


class Session:
    def __init__(self, root: Path):
        self.root = root
        self._last: Path | None = None
        self._dirs: list[Path] = []

    def workdir(self, continued: bool) -> Path:
        if continued:
            if self._last is None:
                raise SpecError("(continued) has no previous section to continue from")
            return self._last
        self._last = Path(tempfile.mkdtemp(dir=self.root))
        self._dirs.append(self._last)
        return self._last

    def cleanup(self) -> None:
        for directory in self._dirs:
            shutil.rmtree(directory, ignore_errors=True)


def execute(test: SpecCase, workdir: Path, repo_root: Path) -> None:
    context = Context(workdir, repo_root)
    steps = test.steps[test.inherited_steps :] if test.continued else test.steps
    for step in steps:
        step.apply(context)
    context.check_default_exit()
