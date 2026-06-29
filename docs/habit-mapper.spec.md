# Habit Mapper Interface

`habit-mapper` reads a findings array as JSON on stdin, groups the findings by
smell, renders each smell's guide, and sets the exit code from each smell's
severity — `enforced` fails the run (exit 1), `suggested` coaches but exits 0.
The finding shape it consumes is the contract in
[sensor-interface.spec.md](sensor-interface.spec.md); how guides resolve through
the ordered plugins is in [architecture.md](architecture.md).

```bash
habit-mapper() { ../../habit-mapper; }
```

## Rendering Jinja2 guides

A `guides/<smell>.md` template renders (Jinja2) against the whole finding. It
reads smell-level facts straight off `details`, and loops over `issues` for the
per-occurrence ones — each issue carries its own `details` bag:

📄.habit-hooks/generic/guides/too-many-parameters.md
```markdown
The following function definitions have more than {{ details.maxAllowed }} parameters:

{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }}
    {{ v.details.signature }} has {{ v.details.actual }} parameters
{% endfor %}
Bundle related arguments into an object.
```

### A smell renders its guide and blocks the run

`too-many-parameters` is `enforced`, so the guide prints and the run fails.

⌨️
```json
[
  {
    "smell": "too-many-parameters",
    "details": { "maxAllowed": 3 },
    "issues": [
      {
        "key": "src/billing.ts",
        "details": {
          "file": "src/billing.ts",
          "line": 2,
          "actual": 4,
          "signature": "bill(customer, items, discount, tax)"
        }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── too-many-parameters (1 issue) ──

The following function definitions have more than 3 parameters:

src/billing.ts:2
    bill(customer, items, discount, tax) has 4 parameters

Bundle related arguments into an object.
```

### Every issue of a smell renders in one guide

The guide is rendered once per smell; its loop walks every issue in the finding.

⌨️
```json
[
  {
    "smell": "too-many-parameters",
    "details": { "maxAllowed": 3 },
    "issues": [
      {
        "key": "src/billing.ts",
        "details": {
          "file": "src/billing.ts",
          "line": 2,
          "actual": 4,
          "signature": "bill(customer, items, discount, tax)"
        }
      },
      {
        "key": "src/report.ts",
        "details": {
          "file": "src/report.ts",
          "line": 8,
          "actual": 5,
          "signature": "render(rows, columns, theme, locale, page)"
        }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── too-many-parameters (2 issues) ──

The following function definitions have more than 3 parameters:

src/billing.ts:2
    bill(customer, items, discount, tax) has 4 parameters
src/report.ts:8
    render(rows, columns, theme, locale, page) has 5 parameters

Bundle related arguments into an object.
```

### Multiple smells each render their own guide

Every finding is framed by a banner — `── <smell> (<n> issue[s]) ──` — so the
findings read as distinct blocks instead of one wall of prose. The banner is
always present, one finding or many, for a consistent shape. The exit code is the
most severe (here `too-many-parameters` is `enforced`).

📄.habit-hooks/generic/guides/warning-comment.md
```markdown
{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }} {{ v.details.message }}
{% endfor %}
Resolve or remove these markers before merging.
```

⌨️
```json
[
  {
    "smell": "too-many-parameters",
    "details": { "maxAllowed": 3 },
    "issues": [
      {
        "key": "src/billing.ts",
        "details": {
          "file": "src/billing.ts",
          "line": 2,
          "actual": 4,
          "signature": "bill(customer, items, discount, tax)"
        }
      },
      {
        "key": "src/report.ts",
        "details": {
          "file": "src/report.ts",
          "line": 8,
          "actual": 5,
          "signature": "render(rows, columns, theme, locale, page)"
        }
      }
    ]
  },
  {
    "smell": "warning-comment",
    "details": {},
    "issues": [
      {
        "key": "src/api.ts",
        "details": { "file": "src/api.ts", "line": 14, "message": "TODO handle retry" }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── too-many-parameters (2 issues) ──

The following function definitions have more than 3 parameters:

src/billing.ts:2
    bill(customer, items, discount, tax) has 4 parameters
src/report.ts:8
    render(rows, columns, theme, locale, page) has 5 parameters

Bundle related arguments into an object.

── warning-comment (1 issue) ──

src/api.ts:14 TODO handle retry

Resolve or remove these markers before merging.
```

## Severity sets the exit code

### A suggested smell coaches but stays green

`warning-comment` is `suggested`, so its guide prints but the run still passes.

📄.habit-hooks/generic/guides/warning-comment.md
```markdown
{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }} {{ v.details.message }}
{% endfor %}
Resolve or remove these markers before merging.
```

⌨️
```json
[
  {
    "smell": "warning-comment",
    "details": {},
    "issues": [
      {
        "key": "src/api.ts",
        "details": { "file": "src/api.ts", "line": 14, "message": "TODO handle retry" }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ✅
```text
── warning-comment (1 issue) ──

src/api.ts:14 TODO handle retry

Resolve or remove these markers before merging.
```

### A clean run prints the pass reminder

No findings on stdin means nothing to coach; the run renders the no-findings guide.

📄.habit-hooks/generic/guides/clean.md
```markdown
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

```bash
habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

## Routing every smell

### Config can point a smell at another guide

A smell's `guide` override replaces the default `<smell>.md`.

📄.habit-hooks/config.toml
```toml
[smells.too-many-parameters]
guide = "compact.md"
```

📄.habit-hooks/generic/guides/compact.md
```markdown
{{ issues | length }} function(s) over {{ details.maxAllowed }} parameters. Bundle arguments into an object.
```

⌨️
```json
[
  {
    "smell": "too-many-parameters",
    "details": { "maxAllowed": 3 },
    "issues": [
      {
        "key": "src/billing.ts",
        "details": {
          "file": "src/billing.ts",
          "line": 2,
          "actual": 4,
          "signature": "bill(customer, items, discount, tax)"
        }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── too-many-parameters (1 issue) ──

1 function(s) over 3 parameters. Bundle arguments into an object.
```

### A finding's language selects a plugin's guide

To coach a `(smell, language)`, the mapper walks the `plugins` list in order and
takes the first plugin that has a guide for that smell and language, falling back
to `generic` last (see [architecture.md](architecture.md)). Here a finding
carries `language = "typescript"`, so the `typescript` plugin's guide wins over
the generic one.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript", "generic"]
```

📄.habit-hooks/generic/guides/loose-equality.md
```markdown
Replace `==`/`!=` with a strict comparison.
```

📄.habit-hooks/typescript/guides/loose-equality.md
```markdown
Use `===`/`!==`; TypeScript will not coerce types for you.
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "language": "typescript",
    "details": {},
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 3 } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── loose-equality (1 issue) ──

Use `===`/`!==`; TypeScript will not coerce types for you.
```

### An earlier plugin's guide wins over a later one

When two plugins both have a guide for the same `(smell, language)`, the one
listed earlier in `plugins` wins. Both `biome` and `eslint` speak `typescript`
and ship a `loose-equality` guide; `biome` is listed first, so its guide renders.

📄.habit-hooks/config.toml
```toml
plugins = ["biome", "eslint", "generic"]
```

📄.habit-hooks/biome/guides/loose-equality.md
```markdown
biome: prefer `===`/`!==` over loose equality.
```

📄.habit-hooks/eslint/guides/loose-equality.md
```markdown
eslint: prefer `===`/`!==` over loose equality.
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "language": "typescript",
    "details": {},
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 3 } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── loose-equality (1 issue) ──

biome: prefer `===`/`!==` over loose equality.
```

### An unknown smell escalates with the default guidance

A smell with no catalogue entry has no tuned guide. It defaults to `enforced`
and renders the generic `uncoached.md` guidance, so it fails the run rather than
slipping through.

⌨️
```json
[
  {
    "smell": "mystery-rule",
    "details": {},
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── mystery-rule (1 issue) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.
```

### A catalogued smell with no resolvable guide falls back to uncoached

A smell can be in the catalogue yet ship no guide for it (here `duplicate-import`
is `enforced` but has no `duplicate-import.md`). Rather than crash, the mapper
falls back to the generic `uncoached.md` guidance, so the run still coaches and
fails on the enforced smell.

⌨️
```json
[
  {
    "smell": "duplicate-import",
    "details": {},
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── duplicate-import (1 issue) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.
```

## Config overrides

### Demoting a smell to suggested keeps the run green

`severity` in config overrides the catalogue default, so an otherwise blocking
smell stops failing the run.

📄.habit-hooks/config.toml
```toml
[smells.too-many-parameters]
severity = "suggested"
```

⌨️
```json
[
  {
    "smell": "too-many-parameters",
    "details": { "maxAllowed": 3 },
    "issues": [
      {
        "key": "src/billing.ts",
        "details": {
          "file": "src/billing.ts",
          "line": 2,
          "actual": 4,
          "signature": "bill(customer, items, discount, tax)"
        }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ✅

## Executable guides

A guide with a non-`.md` extension is run by the **fix runner** registered for
that extension ([config.md](config.md)): the mapper runs `<runner> <guide>` with
the finding on stdin, shows its stdout/stderr, and uses its exit code for
pass/fail. No runner ships by default — register one in config.

### A guide script runs via its fix runner

Exit `0` does not block, even for an enforced smell.

📄.habit-hooks/config.toml
```toml
[runners]
sh = "bash"
```

📄.habit-hooks/generic/guides/oversized-file.sh
```sh
echo "src/legacy.ts is too large — split it into focused modules."
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "lines": 800 },
    "issues": [
      { "key": "src/legacy.ts", "details": { "file": "src/legacy.ts" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ✅
```text
── oversized-file (1 issue) ──

src/legacy.ts is too large — split it into focused modules.
```

### A failing fix runner blocks an enforced smell

A non-zero exit fails the run; the runner's stderr is shown.

📄.habit-hooks/config.toml
```toml
[runners]
sh = "bash"
```

📄.habit-hooks/generic/guides/oversized-file.sh
```sh
echo "Could not auto-split; manual extraction needed." >&2
exit 1
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "lines": 800 },
    "issues": [
      { "key": "src/legacy.ts", "details": { "file": "src/legacy.ts" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1

🚨
```text
Could not auto-split; manual extraction needed.
```
