"""The smell map in ``sensors/eslint.toml``, against the rule IDs eslint emits.

A rule the map does not name arrives under its raw ID — uncoached, and keyed
differently from the same smell everywhere else in the vocabulary, so a snooze
recorded against it matches nothing. typescript-eslint v8 ships an extension rule
for two of the base rules this sensor maps, and a project on its documented setup
enables the extension rather than the base; both are covered here, and they are
the only two, because the remaining nine base rules have no TypeScript twin.

Every case runs the real eslint, because a smell map is only true of the messages
the tool actually emits.
"""

from __future__ import annotations

from pathlib import Path

from eslint_project import SHIPPED_CONFIG, project, sensor_findings

MANY_PARAMETERS_TS = """export function buildOrder(
  a: string, b: string, c: string, d: string,
): string {
  return a + b + c + d;
}
"""

TYPESCRIPT_MAX_PARAMS_CONFIG = """import parser from "@typescript-eslint/parser";
import plugin from "@typescript-eslint/eslint-plugin";

export default [
  {
    files: ["**/*.ts"],
    languageOptions: { parser },
    plugins: { "@typescript-eslint": plugin },
    rules: { "@typescript-eslint/max-params": ["error", { max: 3 }] },
  },
];
"""


def test_the_typescript_rule_arrives_as_the_unused_variable_smell(
    tmp_path: Path,
) -> None:
    """The shipped config reports through the TypeScript rule, so the map has to
    name it or the pairing fix pushes the finding out of the vocabulary."""
    consumer = project(tmp_path)
    (consumer / "eslint.config.mjs").write_bytes(SHIPPED_CONFIG.read_bytes())

    findings = sensor_findings(consumer)

    assert [finding["smell"] for finding in findings] == ["unused-variable"], findings
    assert findings[0]["issues"][0]["details"]["source"] == (
        "eslint:@typescript-eslint/no-unused-vars"
    )


def test_the_typescript_max_params_rule_arrives_as_too_many_parameters(
    tmp_path: Path,
) -> None:
    """The project's own config enables typescript-eslint's extension rule, so the
    finding must land on the same smell — and the same snooze key — as the base
    rule's does anywhere else in the vocabulary."""
    consumer = project(tmp_path)
    (consumer / "eslint.config.mjs").write_text(
        TYPESCRIPT_MAX_PARAMS_CONFIG, encoding="utf-8"
    )
    (consumer / "src" / "repository.ts").write_text(
        MANY_PARAMETERS_TS, encoding="utf-8"
    )

    findings = sensor_findings(consumer)

    assert [finding["smell"] for finding in findings] == [
        "too-many-parameters"
    ], findings
    assert findings[0]["issues"][0]["details"]["source"] == (
        "eslint:@typescript-eslint/max-params"
    )
