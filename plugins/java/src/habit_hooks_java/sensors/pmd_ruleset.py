"""Decide which ruleset PMD is run with.

PMD never discovers a project ruleset on its own — ``-R`` is required — so the
answer is chosen here: a ``--rulesets``/``-R`` among the sensor's ``args`` (the
project naming its config explicitly) wins; then the first conventional ruleset
file the Java ecosystem's build tools point at, in the project directory only;
then the plugin's bundled ``pmd-ruleset.xml`` as the answer to "the project has
none".
"""

from __future__ import annotations

from pathlib import Path

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

RULESET_OPTIONS = ("--rulesets", "-R")
# The attached spellings picocli also takes, longest prefix first so `-R=x` is
# not read as a bare `-R` with `=x` on it. A spelling missed here does not fall
# back: the project's `-R` stays in the tail, ours goes in beside it, and PMD
# unions the two rulesets rather than using theirs.
ATTACHED_RULESET_PREFIXES = ("--rulesets=", "-R=", "-R")


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
