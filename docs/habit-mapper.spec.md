# Habit Mapper Interface

`habit-mapper` reads a findings array as JSON on stdin, groups the findings by
smell, renders each smell's guide, and sets the exit code from each smell's
severity — `enforced` fails the run (exit 1), `suggested` coaches but exits 0.
An **empty** stdin is not a findings array: it is a stage that died before
writing one, so it is coached as an incomplete run and exits 2, the code
reserved for a failure of the tool itself (#103).
The finding shape it consumes is the contract in
[sensor-interface.spec.md](sensor-interface.spec.md); how guides resolve through
the ordered plugins is in [architecture.md](architecture.md).

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

An empty findings array is a stage that ran and found nothing, so there is
nothing to coach; the run renders the no-findings guide.

📄.habit-hooks/generic/guides/clean.md
```markdown
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

⌨️
```json
[]
```

```bash
habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

### An incomplete run is coached, never rendered clean

`incomplete-run` is the reserved smell the sensors stage raises against itself
when a tool broke ([habit-sensors.spec.md](habit-sensors.spec.md)). It is
`enforced` and ships a core guide, so the mapper coaches it and fails the run
rather than rendering the clean guide over broken tooling — even when no plugin
supplies a guide for it (#88). Its issues carry each failure notice as `content`.

⌨️
```json
[
  {
    "smell": "incomplete-run",
    "details": {},
    "issues": [
      {
        "key": "habit-sensors: sensor 'comment' failed: Cannot find module 'ts-morph'",
        "details": { "content": "habit-sensors: sensor 'comment' failed: Cannot find module 'ts-morph'" }
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
── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-sensors: sensor 'comment' failed: Cannot find module 'ts-morph'
Fix the broken tool and re-run; do not treat this change as checked.
```

### Nothing on stdin is an incomplete run, and a tool error

The reserved finding above can only travel when the sensors stage lives long
enough to write it. A stage that dies first — a missing plugin, a rejected
config, an unresolvable ref — writes nothing at all, and a completed run always
writes at least `[]`, so zero bytes is unambiguous. The mapper raises the same
reserved finding against itself and coaches it, because the ✅ line is what an
agent reads as permission to stop. The exit code is **2**, not 1: the run failed
because the tool broke, not because the code has a smell
([cli.py's contract](../src/habit_hooks/cli.py), #103).

```bash
habit-mapper < /dev/null
```

🖥️ ❌ 2
```text
── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-mapper: nothing arrived on stdin — the sensors stage exited before it wrote any findings
Fix the broken tool and re-run; do not treat this change as checked.
```

### A disabled `incomplete-run` still cannot report a clean scan

`[smells.<smell>] disabled` speaks about code smells. It is not a licence to
render the pass reminder over a scan that never happened, so the empty-stream
path renders and fails regardless of it.

📄.habit-hooks/config.toml
```toml
[smells.incomplete-run]
disabled = true
```

```bash
habit-mapper < /dev/null
```

🖥️ ❌ 2
```text
── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-mapper: nothing arrived on stdin — the sensors stage exited before it wrote any findings
Fix the broken tool and re-run; do not treat this change as checked.
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

### A custom smell renders its paired guide

A smell outside the catalogue, declared under `[smells.<name>]` and paired with a
`guides/<name>.md`, renders that guide instead of escalating with the generic
`uncoached.md` prompt.

📄.habit-hooks/config.toml
```toml
[smells.custom-marker]
severity = "enforced"
```

📄.habit-hooks/generic/guides/custom-marker.md
```markdown
Remove the custom marker before shipping.
```

⌨️
```json
[
  {
    "smell": "custom-marker",
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
── custom-marker (1 issue) ──

Remove the custom marker before shipping.
```

### A finding's language selects a plugin's guide

To coach a `(smell, language)`, the mapper takes the first plugin whose declared
language matches the finding, in `plugins` order, then falls back to the
languageless `generic` last (see [architecture.md](architecture.md)). Here
`generic` is listed **first**, yet the finding carries `language = "typescript"`,
so the `typescript` plugin's guide still wins — a matching language beats list
order.

📄.habit-hooks/config.toml
```toml
plugins = ["generic", "typescript"]
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

### An unknown smell is coached with the default guidance, and stays green

A smell with no catalogue entry has no tuned guide, so it renders the generic
`uncoached.md` guidance. It does not fail the run: the catalogue is the record of
what this product has decided is worth failing a build over, and a name absent
from it has had no such decision made about it. Surfacing it keeps the finding
visible without turning someone else's vocabulary into a gate — and the root
`uncoached` key ([config.md](config.md)) moves that answer for a project that
wants `ignore` or `enforce` instead.

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

🖥️ ✅
```text
── mystery-rule (1 issue) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.

src/x.ts
```

### A catalogued smell whose plugin isn't configured falls back to uncoached

Every catalogued smell ships a guide, but in the plugin that owns it — so a
project that doesn't run that plugin has no guide to resolve. Here
`var-declaration` is `enforced` and ships in the `typescript` plugin, which this
project (`biome`, `eslint`, `generic`) does not run, so no configured plugin
supplies `var-declaration.md`. Rather than crash, the mapper falls back to the
generic `uncoached.md` guidance, so the run still coaches and fails on the
enforced smell. Because `uncoached.md` serves any smell shape, its listing is
adaptive: it renders `file:line` for a point-located issue and a bare `file` for
a whole-file one, appending `content` only when present.

⌨️
```json
[
  {
    "smell": "var-declaration",
    "details": {},
    "issues": [
      { "key": "src/a.ts:2", "details": { "file": "src/a.ts", "line": 2, "content": "import x from 'x'" } },
      { "key": "src/b.ts:9", "details": { "file": "src/b.ts", "line": 9 } },
      { "key": "src/c.ts", "details": { "file": "src/c.ts" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── var-declaration (3 issues) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.

src/a.ts:2  import x from 'x'
src/b.ts:9
src/c.ts
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

### A disabled smell is neither coached nor counted

`disabled` drops the smell before routing: no guide renders for it, and it cannot
fail the run. Here the enforced `too-many-parameters` is disabled, so only the
suggested `warning-comment` coaches and the run stays green.

📄.habit-hooks/config.toml
```toml
[smells.too-many-parameters]
disabled = true
```

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

🖥️ ✅
```text
── warning-comment (1 issue) ──

src/api.ts:14 TODO handle retry

Resolve or remove these markers before merging.
```

### Disabling every reported smell leaves a clean run

With its only smell disabled there is nothing left to coach, so the run renders
the no-findings guide, exactly as if the sensor had never reported it.

📄.habit-hooks/config.toml
```toml
[smells.too-many-parameters]
disabled = true
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
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

### `uncoached = "ignore"` drops a smell nobody catalogued

`ignore` takes the other answer to the same question: a smell the catalogue does
not name is dropped through the same seam as `[smells.<name>] disabled` — neither
coached nor counted. The catalogued `warning-comment` beside it still coaches, so
this is the unknown name being dropped, not the run going quiet.

📄.habit-hooks/config.toml
```toml
uncoached = "ignore"
```

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
    "smell": "mystery-rule",
    "details": {},
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts" } }
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

🖥️ ✅
```text
── warning-comment (1 issue) ──

src/api.ts:14 TODO handle retry

Resolve or remove these markers before merging.
```

### `uncoached = "enforce"` fails the run on a smell nobody catalogued

`enforce` holds the line that anything a sensor reports must be either fixed or
given a home in config. The same finding that stays green by default now blocks.

📄.habit-hooks/config.toml
```toml
uncoached = "enforce"
```

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

### A declared severity outranks the `uncoached` policy

Declaring `[smells.<name>] severity` is the project deciding about that one
smell, which takes it out of the policy's reach. Here everything unknown is
dropped, yet `mystery-rule` — declared `enforced` and paired with its own guide —
still coaches and still fails the run.

📄.habit-hooks/config.toml
```toml
uncoached = "ignore"

[smells.mystery-rule]
severity = "enforced"
```

📄.habit-hooks/generic/guides/mystery-rule.md
```markdown
This project has decided about this one.
```

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

This project has decided about this one.
```

### A misspelled `uncoached` value is rejected, not read as a default

A value nothing consumes is a typo the same way a key is, and reading `supress`
as the default would silently mean the opposite of what was intended. The run
stops with the tool-error exit 2, naming the key, what was written, and the three
values it accepts.

📄.habit-hooks/config.toml
```toml
uncoached = "supress"
```

⌨️
```json
[]
```

```bash
habit-mapper
```

🖥️ ❌ 2

🚨
```text
habit-mapper: unknown 'uncoached' value 'supress' in the project config; known values: 'enforce', 'ignore', 'suggest'
```

### An explicit `--config` is read instead of the default file

`habit-mapper --config <path>` loads the whole config — `[smells.*]`, `[runners]`
and the `plugins` order — from that file, not `.habit-hooks/config.toml`. So a CI
config that demotes a smell is honoured even though the checked-in default would
enforce it. Here the default file leaves `too-many-parameters` enforced and only
`ci.toml` demotes it; the run exits 0, proving the named file won.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄ci.toml
```toml
plugins = ["generic"]

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
habit-mapper --config ci.toml
```

🖥️ ✅

### A misspelled key in that config names the mapper, not the sensors

The config loader is shared with `habit-sensors`, but the message must name the
binary the user actually ran: `severty` reaches the mapper through its own
`--config`, so a prefix hardcoded to the other stage sends the reader hunting in
the wrong tool. The run stops before rendering anything, with the tool-error
exit 2 a bad config key always uses.

📄ci.toml
```toml
plugins = ["generic"]

[smells.duplicated-code]
severty = "suggested"
```

⌨️
```json
[]
```

```bash
habit-mapper --config ci.toml
```

🖥️ ❌ 2

🚨
```text
habit-mapper: unknown config key 'severty' in [smells.duplicated-code]; known keys: disabled, guide, severity
```

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

## Core baseline fallback (works without generic)

The baseline `clean.md` and `uncoached.md` guides ship in the core, so the mapper
coaches and never crashes even when no plugin supplies them, e.g. a project that
runs the `python` plugin without `generic`.

### A python-only config coaches an unguided smell via the core uncoached guide

`warning-comment` has no guide in the `python` plugin and `generic` is not
configured, so the mapper falls back to the core `uncoached.md` rather than
crashing. The smell is `suggested`, so the run still passes.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
```

⌨️
```json
[{"smell":"warning-comment","details":{},"issues":[{"key":"x.py:4","details":{"file":"x.py","line":4}}]}]
```

```bash
habit-mapper
```

🖥️ ✅
```text
── warning-comment (1 issue) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.

x.py:4
```

### A python-only clean run prints the core pass reminder

With no findings and no `generic`, the run still renders the core `clean.md`.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
```

⌨️
```json
[]
```

```bash
habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```
