# Smell vocabulary

The canonical, tool-independent catalogue of code smells. Sensors translate
raw tool output *into* these keys; the mapper routes *from* them to guidance.

## Naming rules

- **kebab-case**, lowercase, no namespace prefix (`too-many-parameters`,
  not `size/too-many-parameters` or `eslint:max-params`).
- Name the **smell**, never the tool or the tool's rule ID.
- A key may be language-specific (`explicit-any`) but must not be
  tool-specific.
- The default guide for a smell is `guides/<smell>.md` (the key, verbatim).

A smell may define the shape of the smell-level `details` and of each issue's
`details` (per-occurrence) that its sensors must provide and its prompt template
consumes — e.g. `duplicated-code` carries the duplicated block and its
occurrences, not just a single `file`/`line`. See the finding contract in
[sensor-interface.spec.md](sensor-interface.spec.md).

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
| `unused-class-member`       | Unused class member                   | enforced         |
| `unused-file`               | Unused file                           | enforced         |
| `unused-export`             | Unused export                         | enforced         |
| `test-only-dead-code`       | Dead code alive only via a test       | enforced         |
| `unused-dependency`         | Unused dependency                     | enforced         |
| `unused-import`             | Unused import                         | enforced         |
| `swallowed-exception`       | Swallowed exception                   | suggested        |
| `parse-error`               | Parse / config error                  | enforced         |

`unused-import` was added as a general smell (agent decision) so ruff `F401`
has a canonical home; see `DECISIONS.md`.

`swallowed-exception` is the first smell sourced only from ruff (`BLE001`), with
no TypeScript twin; it carries `source: 'ruff'`. See `DECISIONS.md`.

## TypeScript/JavaScript plugin translation

The raw rule IDs the TS/JS plugin's sensors translate into the smell keys (no
map-block), and the smell key each maps to.

| Raw key (tool:rule)                               | Smell key                   |
|---------------------------------------------------|-----------------------------|
| `eslint:max-lines-per-function`                   | `oversized-function`        |
| `eslint:max-params`                               | `too-many-parameters`       |
| `eslint:@typescript-eslint/max-params`            | `too-many-parameters`       |
| `eslint:complexity`                               | `high-complexity`           |
| `eslint:max-depth`                                | `deep-nesting`              |
| `eslint:max-lines`                                | `oversized-file`            |
| `eslint:no-unused-vars`                           | `unused-variable`           |
| `eslint:@typescript-eslint/no-unused-vars`        | `unused-variable`           |
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
| `knip:classMembers`, `knip:enumMembers`           | `unused-class-member`       |
| `knip:files`                                      | `unused-file`               |
| `knip:exports`, `knip:types`, `knip:nsExports`, `knip:nsTypes` | `unused-export` |
| `knip:dependencies`                               | `unused-dependency`         |
| `knip:production:*`                               | `test-only-dead-code`       |
| `eslint:fatal`                                    | `parse-error`               |

The knip sensor runs two passes when the config marks production patterns with a
trailing `!`. The default pass produces the `knip:<key>` smells above; the gated
`knip --production` pass contributes the dead code the default pass did not name
(code kept alive only by a test) as `test-only-dead-code`, sourced
`knip:production:<key>`.

A knip key with no row above (`binaries`, `duplicates`, `catalog`, and for now
`unlisted`/`unresolved`) is **dropped at the sensor**. Translating a tool's key
set into this vocabulary is the sensor's job, and a key forwarded under knip's own
name would have no guide and no severity behind it. The eslint sensor is the
deliberate exception — it passes an unmapped rule ID through, because that ID
comes from a config the project wrote and turned on itself.

## Python plugin translation

The raw rule IDs the Python plugin's sensors translate into the smell keys (no
map-block), and the smell key each maps to (the rest of the catalogue is shared —
only the plugin's sensors differ).

| Raw key (tool:rule) | Smell key             |
|---------------------|-----------------------|
| `ruff:C901`         | `high-complexity`     |
| `ruff:PLR0913`      | `too-many-parameters` |
| `ruff:PLR0915`      | `oversized-function`  |
| `ruff:F841`         | `unused-variable`     |
| `ruff:F401`         | `unused-import`       |
| `ruff:BLE001`       | `swallowed-exception` |
| `ruff:invalid-syntax` | `parse-error`       |
| `jscpd:duplication` | `duplicated-code`     |
| `deptry:DEP002`     | `unused-dependency`   |
| `line-count:max-module-lines` | `oversized-file` |

TS-only smells (`explicit-any`, `var-declaration`, …) simply do not appear in
the Python plugin. `oversized-file` has no clean ruff rule, so the Python plugin
reuses the generic line-count sensor (its `--max` threshold, default 200).
`deep-nesting` ships for TypeScript only (ESLint `max-depth`); the Python
equivalent (ruff `PLR1702`) is preview/unstable, so it is deferred rather than
opting into ruff `--preview`.

## PHP plugin translation

The raw rule names PHPMD emits, and the smell key each maps to (the rest of the
catalogue is shared — only the plugin's sensors differ).

| Raw key (tool:rule)         | Smell key             |
|-----------------------------|-----------------------|
| `phpmd:ExcessiveParameterList` | `too-many-parameters` |
| `phpmd:CyclomaticComplexity`   | `high-complexity`     |
| `phpmd:ExcessiveMethodLength`  | `oversized-function`  |
| `phpmd:UnusedLocalVariable`    | `unused-variable`     |
| `line-count:max-module-lines`  | `oversized-file`      |

The PHP plugin runs PHPMD (`codesize,unusedcode` rulesets) through a thin sensor
that normalises PHPMD's exit-2-on-violations and maps its rule names to canonical
smells. Like Python, `oversized-file` has no clean PHPMD rule, so the PHP plugin
reuses the generic line-count sensor — add `generic` to the project's `plugins`
list alongside `php` to get it. PHPMD's `NPathComplexity` overlaps
`CyclomaticComplexity`, so only the latter is mapped to avoid double-reporting the
same function.

## Java plugin translation

The raw rule names PMD emits, and the smell key each maps to (the rest of the
catalogue is shared — only the plugin's sensors differ).

| Raw key (tool:rule)         | Smell key             |
|-----------------------------|-----------------------|
| `pmd:ExcessiveParameterList` | `too-many-parameters` |
| `pmd:CyclomaticComplexity`   | `high-complexity`     |
| `pmd:NcssCount`              | `oversized-function`  |
| `pmd:UnusedLocalVariable`    | `unused-variable`     |
| `pmd:UnnecessaryImport`      | `unused-import`       |
| `pmd:EmptyCatchBlock`        | `swallowed-exception` |

The Java plugin runs PMD (`pmd check --format json`) through a thin sensor that
normalises PMD's exit-4-on-violations and maps its rule names to canonical smells.
PMD 7 no longer ships `ExcessiveMethodLength`/`ExcessiveClassLength`, so
`oversized-function` comes from `NcssCount`, which reports classes, methods and
constructors off one rule — the sensor keeps only the method/constructor
violations (PMD's own message distinguishes them) and drops the class-level ones.
PMD never discovers a project ruleset, so the sensor reaches for one only after
checking the conventional locations (`src/main/resources/pmd/ruleset.xml`,
`pmd/ruleset.xml`, `ruleset.xml`, `pmd.xml`) or a `--rulesets` in its args, then
falls back to the bundled `pmd-ruleset.xml` — a project's own ruleset wins
([config.md](config.md)). PMD 7's `UnnecessaryImport` is the renamed
`UnusedImports`.

## Uncoached smells

A smell with no entry above still renders — through the generic `uncoached.md`
guidance — so a sensor a project wrote itself is always surfaced. It does not
fail the run: this catalogue is the record of what is worth failing a build over,
and a name absent from it has had no such decision made about it. A project moves
that answer with the root `uncoached` key (`suggest` / `ignore` / `enforce`, see
[config.md](config.md)), or per smell with `[smells.<name>] severity`, which wins
over it.
