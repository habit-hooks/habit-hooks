# Smell vocabulary

The canonical, tool-independent catalogue of code smells. Sensors translate
raw tool output *into* these keys; the mapper routes *from* them to guidance.

## Naming rules

- **kebab-case**, lowercase, no namespace prefix (`too-many-parameters`,
  not `size/too-many-parameters` or `eslint:max-params`).
- Name the **smell**, never the tool or the tool's rule ID.
- A key may be language-specific (`explicit-any`) but must not be
  tool-specific.
- The default prompt template for a smell is `<smell>.md` (the key, verbatim).

A smell may define the `details` shape its sensors must provide and its
prompt template consumes — e.g. `duplicated-code` carries the duplicated
block and its occurrences, not just a single `file`/`line`.

## Catalogue

Default severity: `enforced` fails the run (exit 1); `suggested` coaches but
exits 0. The mapper config can override it per project.

| Smell key                   | Title                                 | Default severity |
|-----------------------------|---------------------------------------|------------------|
| `oversized-function`        | Oversized function                    | enforced         |
| `too-many-parameters`       | Too many parameters                   | enforced         |
| `high-complexity`           | High cyclomatic complexity            | enforced         |
| `deep-nesting`              | Deep nesting                          | enforced         |
| `oversized-file`            | Oversized file                        | enforced         |
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
| `needs-extraction`          | Needs extraction                      | enforced         |
| `unused-class-member`       | Unused class member                   | enforced         |
| `unused-file`               | Unused file                           | enforced         |
| `unused-export`             | Unused export                         | enforced         |
| `unused-dependency`         | Unused dependency                     | enforced         |
| `unused-import`             | Unused import                         | enforced         |
| `swallowed-exception`       | Swallowed exception                   | suggested        |
| `parse-error`               | Parse / config error                  | enforced         |

`unused-import` was added as a general smell (agent decision) so ruff `F401`
has a canonical home; see `DECISIONS.md`.

`swallowed-exception` is the first smell sourced only from ruff (`BLE001`), with
no TypeScript twin; it carries `source: 'ruff'`. See `DECISIONS.md`.

## TypeScript/JavaScript preset translation

The raw rule IDs the TS/JS preset sensors emit, and the smell key each maps
to.

| Raw key (tool:rule)                               | Smell key                   |
|---------------------------------------------------|-----------------------------|
| `eslint:max-lines-per-function`                   | `oversized-function`        |
| `eslint:max-params`                               | `too-many-parameters`       |
| `eslint:complexity`                               | `high-complexity`           |
| `eslint:max-depth`                                | `deep-nesting`              |
| `eslint:max-lines`                                | `oversized-file`            |
| `eslint:no-unused-vars`                           | `unused-variable`           |
| `eslint:eqeqeq`                                   | `loose-equality`            |
| `eslint:no-var`                                   | `var-declaration`           |
| `eslint:prefer-const`                             | `non-const-binding`         |
| `eslint:no-duplicate-imports`                     | `duplicate-import`          |
| `eslint:no-warning-comments`                      | `warning-comment`           |
| `eslint:@typescript-eslint/no-explicit-any`       | `explicit-any`              |
| `eslint:@typescript-eslint/no-non-null-assertion` | `non-null-assertion`        |
| `eslint:@typescript-eslint/no-inferrable-types`   | `redundant-type-annotation` |
| `comment:non-essential`                           | `non-essential-comment`     |
| `jscpd:duplication`                               | `duplicated-code`           |
| `knip:classMembers`                               | `unused-class-member`       |
| `knip:files`                                      | `unused-file`               |
| `knip:exports`                                    | `unused-export`             |
| `knip:dependencies`                               | `unused-dependency`         |
| `eslint:fatal`                                    | `parse-error`               |

## Python preset translation

The raw rule IDs the Python preset sensors emit, and the smell key each maps
to (the rest of the catalogue is shared — only the sensor layer differs).

| Raw key (tool:rule) | Smell key             |
|---------------------|-----------------------|
| `ruff:C901`         | `high-complexity`     |
| `ruff:PLR0913`      | `too-many-parameters` |
| `ruff:PLR0915`      | `oversized-function`  |
| `ruff:F841`         | `unused-variable`     |
| `ruff:F401`         | `unused-import`       |
| `ruff:BLE001`       | `swallowed-exception` |
| `jscpd:duplication` | `duplicated-code`     |
| `deptry:DEP002`     | `unused-dependency`   |
| `line-count:max-module-lines` | `oversized-file` |

TS-only smells (`explicit-any`, `var-declaration`, …) simply do not appear in
the Python preset. `oversized-file` has no clean ruff rule, so the Python preset
emits it from a language-agnostic line-count sensor whose threshold
(`max-module-lines`, default 200) is read from the consumer's config text (see
`DECISIONS.md`). `deep-nesting` ships for TypeScript only (ESLint `max-depth`);
the Python equivalent (ruff `PLR1702`) is preview/unstable, so it is deferred
rather than opting the default preset into ruff `--preview`.

## Combinations

Some smells are **composite**: derived by a multi sensor from the co-occurrence
of others, not from a tool (docs/architecture.md "Combinations"). `needs-extraction`
fires when a single file has both `oversized-file` **and** `duplicated-code`. By
default it **augments** (all three smells show); `needsExtraction.replace: true`
suppresses the two input smells for that file so only `needs-extraction` remains.

| Composite          | Derived from                          | Smell key          |
|--------------------|---------------------------------------|--------------------|
| same-file overlap  | `oversized-file` + `duplicated-code`  | `needs-extraction` |

## Uncoached smells

A smell with no configured guidance falls through to an **uncoached** bucket
rather than being dropped, so unknown sensor output is always surfaced.
