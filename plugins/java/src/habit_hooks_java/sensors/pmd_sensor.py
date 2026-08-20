"""Run PMD and print canonical smell findings.

PMD exits 4 when it finds violations, 0 when clean, and 1/2/5 on exceptions,
usage errors and recoverable errors (since 7.3.0) — so a bare pipe cannot tell
a clean run from a crash. This wrapper runs PMD against the scoped files,
treats only 0/4 as success, and shapes each violation into the canonical
finding, mapping PMD rule names to smell keys.

PMD never discovers a project ruleset on its own — ``-R`` is required — so the
ruleset is resolved here: a ``--rulesets`` among the sensor's ``args`` (the
project naming its config explicitly) wins; then the first conventional ruleset
file the Java ecosystem's build tools point at, in the project directory only;
then the plugin's bundled ``pmd-ruleset.xml`` as the answer to "the project has
none".

PMD 7's picocli reads a positional path that directly follows the ruleset value
as another ``-R`` value (``-R ruleset.xml file.java`` analyses nothing), so the
wrapper uses the short forms ``-R`` and per-file ``-d``, which do not. Verified
against PMD 7.26.0.

The sensor's own command spells ``${args} -- ${files}``, so ``sys.argv[1:]``
carries both halves of ``[sensors.pmd] args`` on one side of a literal ``--``
and the scoped files on the other — that is what lets a project pass any PMD
flag (``--aux-classpath``, ``--minimum-priority``, ...) through untouched
instead of every argv token becoming a bogus ``-d`` file argument.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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

# The ruleset names Maven and Gradle PMD setups conventionally point at, in
# the order a project directory is checked. PMD itself offers no discovery
# signal (it never looks one up), so this is the knip-shaped search for the
# project's own config; a ``--rulesets`` in the sensor's args overrides it.
RULESET_LOCATIONS = (
    "src/main/resources/pmd/ruleset.xml",
    "pmd/ruleset.xml",
    "ruleset.xml",
    "pmd.xml",
)

SUCCESS_EXIT_CODES = (0, 4)
RULESET_OPTIONS = ("--rulesets", "-R")
# The attached spellings picocli also takes, longest prefix first so `-R=x` is
# not read as a bare `-R` with `=x` on it. A spelling missed here does not fall
# back: the project's `-R` stays in the tail, ours goes in beside it, and PMD
# unions the two rulesets rather than using theirs.
ATTACHED_RULESET_PREFIXES = ("--rulesets=", "-R=", "-R")


def run_pmd(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """What PMD said, or what a shell says about a PMD nobody installed.

    The plugin does not ship the distribution, so ``pmd`` is the command that
    goes missing — and an absent one raised a ``FileNotFoundError`` out of
    here, making twenty lines of Python internals the sensor's diagnosis
    (#114). This wrapper is what looks for pmd, so it answers the way the
    shell would have, and that phrase is what the run recognises to name the
    missing tool.
    """
    command = ["pmd", "check", "--no-cache", "--format", "json"]
    try:
        return subprocess.run(
            [*command, *arguments], capture_output=True,
            encoding="utf-8", errors="replace",  # sensors.spawn's policy
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "pmd: command not found\n")


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


def ruleset_of(argv: list[str], project: Path) -> tuple[Path, list[str]]:
    """The ruleset in force, and the remaining args with no ruleset named.

    A ``--rulesets``/``-R`` among the sensor's args is the project's own config
    and wins over everything; PMD only ever gets one, so it is pulled out of
    the tail rather than left beside the wrapper's own.
    """
    for i, token in enumerate(argv):
        if token in RULESET_OPTIONS and i + 1 < len(argv):
            return Path(argv[i + 1]), [*argv[:i], *argv[i + 2 :]]
        for prefix in ATTACHED_RULESET_PREFIXES:
            if token.startswith(prefix) and len(token) > len(prefix):
                return Path(token[len(prefix) :]), [*argv[:i], *argv[i + 1 :]]
    for name in RULESET_LOCATIONS:
        if (project / name).is_file():
            return project / name, argv
    return Path(__file__).with_name("pmd-ruleset.xml"), argv


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
    argv = sys.argv[1:]
    if not argv:
        print("[]")
        return 0
    pmd_args, files = split_argv(argv)
    ruleset, remaining_args = ruleset_of(pmd_args, Path.cwd())
    file_args = [token for file in files for token in ("-d", file)]
    result = run_pmd(["-R", str(ruleset), *remaining_args, *file_args])
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
