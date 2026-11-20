# Smell vocabulary

To ensure compatibility between plugins this catalogue defines the most frequently used code smells. All plugins sensors should aim to output these keys where possible, but they may define their own custom keys for unrelated or language-specific smells.

## Catalogue

Default severity: `enforced` fails the run (exit 1); `suggested` coaches but exits 0. The mapper config can override it per project.

| Smell key                   | Title                                 | Default severity |
|-----------------------------|---------------------------------------|------------------|
| `oversized-function`        | Oversized function                    | enforced         |
| `too-many-parameters`       | Too many parameters                   | enforced         |
| `high-complexity`           | High cyclomatic complexity            | enforced         |
| `deep-nesting`              | Deep nesting                          | enforced         |
| `oversized-file`            | Oversized file                        | enforced         |
| `oversized-block`           | Oversized block                       | enforced         |
| `unused-variable`           | Unused variable                       | enforced         |
| `loose-equality`            | Loose equality                        | enforced         |
| `var-declaration`           | `var` declaration                     | enforced         |
| `non-const-binding`         | Reassignable binding never reassigned | enforced         |
| `duplicate-import`          | Duplicate import                      | enforced         |
| `warning-comment`           | Warning comment (TODO/FIXME/…)        | suggested        |
| `explicit-any`              | Explicit `any`                        | suggested        |
| `non-null-assertion`        | Non-null assertion                    | suggested        |
| `redundant-type-annotation` | Redundant type annotation             | enforced         |
| `non-essential-comment`     | Non-essential comment                 | suggested        |
| `duplicated-code`           | Duplicated code                       | suggested        |
| `unused-class-member`       | Unused class member                   | enforced         |
| `unused-file`               | Unused file                           | enforced         |
| `unused-export`             | Unused export                         | enforced         |
| `test-only-dead-code`       | Dead code alive only via a test       | enforced         |
| `unused-dependency`         | Unused dependency                     | enforced         |
| `unused-import`             | Unused import                         | enforced         |
| `swallowed-exception`       | Swallowed exception                   | suggested        |
| `slow-test`                 | Slow test                             | suggested        |
| `parse-error`               | Parse / config error                  | enforced         |

## Proposing new smells

All changes to the list must be approved by core maintainers, and should be submitted for discussion as a separate PR. 

**Guidelines:**
- Smell names should follow established smell names that are well documented in literature
- When no such name exists, name the smell by the problem it creates, not the detection tool or the observation
- For a smell to be approved it must come with a default guide in `guides/<smell>.md` that can be reasonably expected to work with a large number of languages.
