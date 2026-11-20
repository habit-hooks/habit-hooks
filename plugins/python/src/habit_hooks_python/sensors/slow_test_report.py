from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--habit-hooks-report")


def matches_pattern(path: Path, pattern: str) -> bool:
    pattern = pattern.replace("/", os.sep)
    name = str(path.absolute()) if os.sep in pattern else path.name
    if os.sep in pattern and not os.path.isabs(pattern):
        pattern = f"*{os.sep}{pattern}"
    return fnmatch.fnmatch(name, pattern)


def matches_test_pattern(path: str, patterns: list[str]) -> bool:
    return Path(path).name != "conftest.py" and any(
        matches_pattern(Path(path), pattern) for pattern in patterns
    )


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    config = session.config
    if config.option.collectonly or config.option.setuponly:
        raise pytest.UsageError(
            "slow-test requires test execution, not collection/setup only"
        )
    config.args = [
        path
        for path in config.args
        if getattr(config.option, "doctestmodules", False)
        or matches_test_pattern(path, config.getini("python_files"))
    ]


def write_report(config: pytest.Config, data: dict) -> None:
    if not hasattr(config, "workerinput"):
        Path(config.getoption("--habit-hooks-report")).write_text(
            json.dumps(data), encoding="utf-8"
        )


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(Timings(config), "habit-hooks-timings")


class Timings:
    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.current: dict[tuple[str, str], float] = {}
        self.durations: dict[str, float] = {}
        self.collection_failed = False

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        self.collection_failed |= report.failed

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        key = (getattr(report, "worker_id", ""), report.nodeid)
        if report.when == "setup":
            self.current[key] = 0.0
        self.current[key] = self.current.get(key, 0.0) + report.duration
        self.durations[report.nodeid] = max(
            self.durations.get(report.nodeid, 0.0), self.current[key]
        )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        write_report(
            self.config,
            {
                "collected": session.testscollected,
                "collection_failed": self.collection_failed,
                "durations": self.durations,
            },
        )
