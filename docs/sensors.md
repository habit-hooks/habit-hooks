# Sensors

A sensor **finds smells**. It runs a tool (or scans the AST directly) and
appends `Issue`s to the bag, translating its tool's raw output into canonical
[smell keys](smell-vocabulary.md).

## Contract

```ts
interface Sensor {
  id: string;
  produces: string[];                 // smell keys this sensor can emit
  dependsOn?: string[];               // smell keys it consumes (multi sensors)
  run(ctx: SensorContext): Promise<Issue[]>;
}

interface SensorContext {
  files: string[];
  cwd: string;
  deps: Issue[];                      // issues for the smells listed in dependsOn
}

interface Issue {
  smell: string;                      // canonical key (kebab-case) — the routing key
  details: Record<string, unknown>;   // everything relevant to this smell
}
```

`smell` is the only field with a fixed meaning. `details` is the open bag:
the sensor fills it with whatever fits the smell. Use the conventional common
fields (`file`, `line`, `column`, `message`, `source`) where they apply so
prompts can rely on them; smells that aren't file/line-shaped carry whatever
structure suits them.

Sensors are **additive** (each appends to the bag) and **deterministic**
(detection is mechanical, no judgement).

A sensor must never throw on tool spawn/timeout failure. Instead the failure
surfaces as a stderr notice with zero issues for that tool, and **fails the run
(exit 1)** — a broken tool is a failed run, not a false-clean. Every other
sensor that ran successfully still contributes its full output; only the overall
exit code reflects the failure (independent of whether any violations were
found).

## Sensor runner

The runner registers every configured sensor and runs them in dependency
order.

- A sensor declares the smells it `produces`. A **multi sensor** also
  declares the smells it `dependsOn` — **smells, not sensors**.
- The runner maps each depended-on smell to the sensor(s) that produce it,
  builds a dependency graph, and orders the run so every producer of a multi
  sensor's input smells has finished before it starts.
- A multi sensor receives those producers' issues in `ctx.deps` and emits
  derived smells (e.g. `oversized-file` + `duplicated-code` in one file →
  `needs-extraction`). This is how combination smells work, keeping the
  mapper a pure single-smell function.
- Unsatisfiable dependencies or dependency cycles are a startup error.

Leaf sensors leave `dependsOn` unset and ignore `ctx.deps`.

## Language presets

No sensors are enabled by default. `init` asks which language the project
uses and installs only the sensors for that language. The
TypeScript/JavaScript preset:

| Sensor    | Tool              | Smells produced                                                            |
|-----------|-------------------|----------------------------------------------------------------------------|
| `eslint`  | ESLint            | size/complexity/correctness/TS smells, `parse-error`                       |
| `knip`    | knip              | `unused-file`, `unused-export`, `unused-dependency`, `unused-class-member` |
| `jscpd`   | jscpd             | `duplicated-code`                                                          |
| `comment` | ts-morph AST scan | `non-essential-comment`                                                    |

Each preset sensor owns its raw → smell translation (see
[smell-vocabulary.md](smell-vocabulary.md)). A preset is a starting point;
add, remove, or replace sensors in config.

## Integrating other tools

A sensor's output must be bag JSON:
`{ "issues": [ { "smell", "details" } ] }`. Two ways to get there.

### Wrapper script (default)

Wrap any tool in a script that runs it and prints bag JSON. This is the
universal path — the script can reshape anything and owns the raw → smell
translation.

```jsonc
{ "sensors": { "ruff": { "command": "scripts/ruff-sensor.sh ${files}" } } }
```

`${files}` expands to the scoped file list; the command prints bag JSON to
stdout.

### Declarative adapter (convenience)

When a tool already emits JSON, skip the script and declare how to read it.
The adapter extracts each issue, maps field names into the bag, and
translates raw keys to smells. Up to two levels of array nesting are
supported, which covers the common toolchains.

Flat list (Ruff, pylint, most Python/JS tools):

```jsonc
{
  "sensors": {
    "ruff": {
      "command": "ruff check --output-format=json ${files}",
      "items": "[]",                 // each element is one issue
      "fields": {                    // bag field ← dot-path in the issue
        "smell":   "code",
        "file":    "filename",
        "line":    "location.row",
        "column":  "location.column",
        "message": "message"
      },
      "map": { "R0913": "too-many-parameters", "C901": "high-complexity" }
    }
  }
}
```

Nested (ESLint groups messages under each file):

```jsonc
{
  "sensors": {
    "eslint": {
      "command": "eslint -f json ${files}",
      "group": "[]",                 // outer array: one entry per file
      "items": "messages[]",         // inner array: the issues
      "fields": {
        "smell":   "ruleId",
        "file":    "group.filePath", // "group." reads the outer entry
        "line":    "line",
        "column":  "column",
        "message": "message"
      },
      "map": { "max-params": "too-many-parameters", "complexity": "high-complexity" }
    }
  }
}
```

- `fields` is the field-name map: each bag field is filled from a dot-path in
  the source (prefix `group.` to read the outer entry).
- `map` rewrites the raw `smell` value to a canonical key; the raw key is
  kept in `details.source`. Omit for identity passthrough.
- Anything the adapter cannot express falls back to a wrapper script.

## More sensor wrappers (long term)

Limit, fail-fast, change-set, and cache are sensors that wrap other sensors,
expressible against this contract without changing it. Added as needed.
