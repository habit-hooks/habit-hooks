from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_BUDGET_SECONDS = 1.0
SUCCESS_EXIT_CODES = {0, 1, 5}
BUDGET_ERROR = "budget must be a positive number of seconds"
NO_DURATION_REPORT = "pytest produced no complete timing report\n"


def positive_seconds(value: str) -> float:
    try:
        budget = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(BUDGET_ERROR) from None
    if not math.isfinite(budget) or budget <= 0:
        raise argparse.ArgumentTypeError(BUDGET_ERROR)
    return budget


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pytest")
    parser.add_argument(
        "--budget", type=positive_seconds, default=DEFAULT_BUDGET_SECONDS
    )
    parser.add_argument("files", nargs="*")
    return parser.parse_args(argv)


def file_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0].replace("\\", "/")


def issue(nodeid: str, duration: float) -> dict:
    path = file_of(nodeid)
    return {
        "key": nodeid,
        "details": {
            "file": path,
            "test": nodeid,
            "duration": duration,
            "content": f"{duration:.2f}s",
            "source": "pytest:durations",
        },
    }


def findings(entries: list[tuple[str, float]], budget: float) -> list[dict]:
    issues = [
        issue(nodeid, duration)
        for nodeid, duration in sorted(entries, key=lambda item: item[1], reverse=True)
        if duration > budget
    ]
    if not issues:
        return []
    return [{"smell": "slow-test", "details": {"maxAllowed": budget}, "issues": issues}]


def run_pytest(
    pytest: str, files: list[str], report: Path
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    helper_dir = str(Path(__file__).resolve().parent)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [env.get("PYTHONPATH"), helper_dir])
    )
    return subprocess.run(
        [
            pytest,
            "-p",
            "slow_test_report",
            "--durations=0",
            "--habit-hooks-report",
            str(report),
            "--",
            *files,
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def report_entries(report: Path) -> list[tuple[str, float]]:
    data = json.loads(report.read_text(encoding="utf-8"))
    if data["collection_failed"] or (data["collected"] and not data["durations"]):
        raise ValueError(NO_DURATION_REPORT)
    return list(data["durations"].items())


def report_from(
    result: subprocess.CompletedProcess[str], report: Path, budget: float
) -> int:
    if result.returncode not in SUCCESS_EXIT_CODES:
        sys.stderr.write(result.stderr or result.stdout)
        return 2
    try:
        entries = report_entries(report)
    except (OSError, ValueError, KeyError, TypeError):
        sys.stderr.write(NO_DURATION_REPORT + (result.stderr or result.stdout))
        return 2
    print(json.dumps(findings(entries, budget)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    files = [path for path in args.files if path.endswith(".py")]
    if not files:
        print(json.dumps([]))
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "timings.json"
        return report_from(run_pytest(args.pytest, files, report), report, args.budget)


if __name__ == "__main__":
    sys.exit(main())
