"""Which config an eslint run gets: the project's own, or the one we ship.

Installing habit-hooks must never override a developer's existing preferences, so
the shipped flat config answers "this project has written none" and nothing else.
Only eslint can say whether the project has one: its lookup runs from each linted
**file's** directory, so a config below the directory habit-hooks was invoked in
is eslint's answer and no walk from that directory would ever see it. The sensor
therefore names no config, and reaches for the shipped one only when eslint
itself reports it could not find any.

Every case runs the real eslint, because a discovery rule is only true of the
tool that does the discovering.
"""

from __future__ import annotations

from pathlib import Path

from eslint_project import UNUSED_LOCAL_LINE, project, sensor_findings, sensor_run

NO_CONSOLE_CONFIG = (
    'export default [{ files: ["**/*.ts"], rules: { "no-console": "error" } }];\n'
)
CONSOLE_TS = 'console.log("shipping this by accident");\n'
UNLOADABLE_CONFIG = 'throw new Error("this project\'s own config is broken");\n'

# Trips `no-console` under the config above and `eqeqeq` under the shipped one,
# so which config ran is legible from the smell alone.
BOTH_TS = 'if (1 == "1") { console.log("shipping this by accident"); }\n'
UNDISCOVERABLE = Path("configs") / "eslint.mjs"


def test_a_flat_config_below_the_project_is_still_the_project_s_own(
    tmp_path: Path,
) -> None:
    """A monorepo linted from its root: eslint looks up from each file, so the
    config beside the package is the one it uses, and habit-hooks must report
    what that config says. Asking the question from the directory habit-hooks
    runs in instead answers "none" and replaces a real config with ours."""
    consumer = project(tmp_path)
    package = consumer / "packages" / "app" / "src"
    package.mkdir(parents=True)
    (consumer / "packages" / "app" / "eslint.config.mjs").write_text(
        NO_CONSOLE_CONFIG, encoding="utf-8"
    )
    (package / "x.ts").write_text(CONSOLE_TS, encoding="utf-8")

    findings = sensor_findings(consumer, ("packages/app/src/x.ts",))

    assert [finding["smell"] for finding in findings] == ["no-console"], findings


def test_a_flat_config_above_the_project_is_still_the_project_s_own(
    tmp_path: Path,
) -> None:
    """The other direction: eslint's lookup walks up, so a monorepo root's config
    is one the project already has. Stopping at the project directory would name
    ours over a config eslint would have found."""
    consumer = project(tmp_path)
    (tmp_path / "eslint.config.mjs").write_text(NO_CONSOLE_CONFIG, encoding="utf-8")
    (consumer / "src" / "repository.ts").write_text(CONSOLE_TS, encoding="utf-8")

    findings = sensor_findings(consumer)

    assert [finding["smell"] for finding in findings] == ["no-console"], findings


def test_a_project_that_wrote_no_config_gets_the_shipped_one(tmp_path: Path) -> None:
    """The fallback #113 exists for. Nothing in the fixture's ancestry is an
    eslint config, so eslint finds none and the shipped one runs — recognisable
    because pairing the base rule off against the TypeScript one is a decision no
    other config here has taken."""
    findings = sensor_findings(project(tmp_path))

    assert [finding["smell"] for finding in findings] == ["unused-variable"], findings
    issue = findings[0]["issues"][0]
    assert issue["details"]["source"] == "eslint:@typescript-eslint/no-unused-vars"
    assert issue["details"]["line"] == UNUSED_LOCAL_LINE


def test_a_config_named_through_the_sensor_s_args_is_the_config_that_runs(
    tmp_path: Path,
) -> None:
    """The documented escape hatch for a config eslint's own lookup cannot reach.

    A project that keeps its config somewhere eslint never looks says so with
    ``[sensors.eslint] args = ["--config", "configs/eslint.mjs"]``. Dropped, those
    args make eslint report no config at all, our fallback answers a question the
    project already answered, and their own rule is never mentioned — a wrong
    answer that reads as a clean run.
    """
    consumer = project(tmp_path)
    (consumer / UNDISCOVERABLE.parent).mkdir()
    (consumer / UNDISCOVERABLE).write_text(NO_CONSOLE_CONFIG, encoding="utf-8")
    (consumer / "src" / "repository.ts").write_text(BOTH_TS, encoding="utf-8")

    findings = sensor_findings(consumer, args=("--config", str(UNDISCOVERABLE)))

    assert [finding["smell"] for finding in findings] == ["no-console"], findings


def test_a_config_eslint_cannot_load_fails_the_run_rather_than_falling_back(
    tmp_path: Path,
) -> None:
    """eslint exits non-zero both when it has findings and when it breaks, so
    "it failed" is not the question — "did it fail for want of a config" is. A
    project whose own config throws has one, and lending it ours would report
    against a config it never asked for and call the run complete."""
    consumer = project(tmp_path)
    (consumer / "eslint.config.mjs").write_text(UNLOADABLE_CONFIG, encoding="utf-8")

    result = sensor_run(consumer)

    assert result.returncode != 0, result.stdout
    assert "this project's own config is broken" in result.stderr, result.stderr
    assert "unused-variable" not in result.stdout, result.stdout
