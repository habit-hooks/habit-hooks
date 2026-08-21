"""Run PMD and print canonical smell findings.

PMD exits 4 when it finds violations, 0 when clean, and 1/2/5 on exceptions,
usage errors and recoverable errors (since 7.3.0) — so a bare pipe cannot tell
a clean run from a crash. This wrapper runs PMD against the scoped files,
treats only 0/4 as success, and shapes each violation into the canonical
finding, mapping PMD rule names to smell keys. Which ruleset it runs with is
the neighbouring ``pmd_ruleset``'s decision.

The sensor is run as a loose script (``${python} ${dir}/pmd_sensor.py``), so its
own directory is ``sys.path[0]`` and that neighbour is a plain top-level import
— the same in the installed package and in a vendored copy, since ``${dir}``
expands to whichever of the two won the override chain.

PMD 7's picocli reads a positional path that directly follows the ruleset value
as another ``-R`` value (``-R ruleset.xml file.java`` analyses nothing), so the
wrapper uses the short forms ``-R`` and per-file ``-d``, which do not. Verified
against PMD 7.26.0.

The sensor's own argv spells ``${detector:pmd} ${args} -- ${files}``, so
``sys.argv[1]`` is the file to run PMD by and ``sys.argv[2:]`` carries both
halves of ``[sensors.pmd] args`` on one side of a literal ``--`` and the scoped
files on the other — that is what lets a project pass any PMD flag
(``--aux-classpath``, ``--minimum-priority``, ...) through untouched instead of
every argv token becoming a bogus ``-d`` file argument.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pmd_ruleset import ruleset_of

RULE_SMELLS = {
    "ExcessiveParameterList": "too-many-parameters",
    "CyclomaticComplexity": "high-complexity",
    "NcssCount": "oversized-function",
    "UnusedLocalVariable": "unused-variable",
    "UnnecessaryImport": "unused-import",
    "EmptyCatchBlock": "swallowed-exception",
}

# NcssCount and CyclomaticComplexity each report classes, methods and
# constructors off one rule, and the catalogue has a smell only for oversized
# and over-complex methods, so class-level violations are dropped. The
# distinction lives in PMD's own message template, which is the only structural
# signal the JSON report carries for it.
METHOD_LEVEL_RULES = ("NcssCount", "CyclomaticComplexity")
METHOD_LEVEL_PREFIXES = ("The method", "The constructor")

SUCCESS_EXIT_CODES = (0, 4)


def run_pmd(pmd: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """What PMD said, run as the file this sensor was handed.

    ``pmd`` is a file and never a name to look up. The plugin declares the tool
    its sensor reaches for, and the run resolves that declaration to the very
    file the setup cleared it by before spawning this helper — which is how the
    ``pmd.bat`` PMD ships is reached on Windows, where a spawn adds ``.exe`` to
    a bare name and nothing else. A PMD nobody installed never reaches here: the
    sensor fails first, named, as the missing command it is.
    """
    return subprocess.run(
        [pmd, "check", "--no-cache", "--format", "json", *arguments],
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # one invalid byte must not take the sensor down
    )


def split_argv(argv: list[str]) -> tuple[list[str], list[str]]:
    """``argv``, split on the last literal ``--``: PMD's own flags before it,
    the files to analyse after.

    The template spells ``${args} -- ${files}``, so the separator sits after
    everything ``args`` can contribute and before every file: the *last* ``--``
    is always ours, whatever a project wrote into its args.
    """
    if "--" not in argv:
        return argv, []
    index = len(argv) - 1 - argv[::-1].index("--")
    return argv[:index], argv[index + 1 :]


def violations(report: dict) -> list[dict]:
    return [
        {"file": entry["filename"], "violation": violation}
        for entry in report.get("files", [])
        for violation in entry["violations"]
    ]


def smell_of(entry: dict) -> str | None:
    violation = entry["violation"]
    rule = violation["rule"]
    if rule in METHOD_LEVEL_RULES and not violation["description"].startswith(
        METHOD_LEVEL_PREFIXES
    ):
        return None
    return RULE_SMELLS.get(rule)


def issue(entry: dict) -> dict:
    violation = entry["violation"]
    return {
        "key": entry["file"],
        "details": {
            "file": entry["file"],
            "line": violation["beginline"],
            "message": violation["description"],
            "source": "pmd:" + violation["rule"],
        },
    }


def findings(entries: list[dict]) -> list[dict]:
    by_smell: dict[str, list[dict]] = {}
    for entry in entries:
        smell = smell_of(entry)
        if smell is not None:
            by_smell.setdefault(smell, []).append(issue(entry))
    return [
        {"smell": smell, "details": {}, "issues": issues}
        for smell, issues in by_smell.items()
    ]


def main() -> int:
    pmd, argv = sys.argv[1], sys.argv[2:]
    if not argv:
        print("[]")
        return 0
    pmd_args, files = split_argv(argv)
    ruleset, remaining_args = ruleset_of(pmd_args, Path.cwd())
    file_args = [token for file in files for token in ("-d", file)]
    result = run_pmd(pmd, ["-R", str(ruleset), *remaining_args, *file_args])
    if result.returncode not in SUCCESS_EXIT_CODES:
        sys.stderr.write(processing_errors(result.stdout) or result.stderr or result.stdout)
        return 2
    print(json.dumps(findings(violations(json.loads(result.stdout)))))
    return 0


def processing_errors(stdout: str) -> str:
    """What a non-successful run actually failed on.

    PMD's own stderr on a recoverable error is a generic "an error occurred,
    report a bug" — while the JSON report it still writes to stdout names the
    file and the parse failure. That message is the one a reader can act on.
    """
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    errors = report.get("processingErrors", [])
    return "".join(f"{entry['filename']}: {entry['message']}\n" for entry in errors)


if __name__ == "__main__":
    sys.exit(main())
