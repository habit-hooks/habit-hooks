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

## Sensors are config-driven

A project's `sensors` map (in `habit-hooks.config.{ts,js,mjs,json}`) is the
single way sensors are assembled — built-in and custom alike. Each entry is
keyed by sensor id and is one of three mutually exclusive `SensorSpec` modes.
The mode is chosen by which keys you set; mixing modes is a validation error.

### `use` — a code-backed built-in

```jsonc
{ "sensors": { "eslint": { "use": "eslint" } } }
```

References a bundled sensor by id. Its `produces`/`dependsOn` come from the
factory, so a `use` entry sets `use` and nothing else. Available built-in ids:

`eslint`, `comment`, `jscpd`, `knip`, `ruff`, `deptry`, `line-count`,
`needs-extraction`.

### Wrapper script

```jsonc
{
  "sensors": {
    "my-sensor": {
      "command": "scripts/x.sh ${files}",
      "produces": ["my-smell"]
    }
  }
}
```

Wrap any tool in a script that runs it and prints bag JSON
(`{ "issues": [ { "smell", "details" } ] }`) to stdout. This is the universal
path — the script can reshape anything and owns the raw → smell translation.
`${files}` expands to the scoped file list. `command` and `produces` are
required; the entry id is the map key.

### Declarative adapter

When a tool already emits JSON, skip the script and declare how to read it.
The adapter extracts each issue, maps field names into the bag, and translates
raw keys to smells. Up to two levels of array nesting are supported, which
covers the common toolchains.

Flat list (Ruff, pylint, most Python/JS tools):

```jsonc
{
  "sensors": {
    "ruff": {
      "command": "ruff check --output-format=json ${files}",
      "produces": ["too-many-parameters", "high-complexity"],
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
      "produces": ["too-many-parameters", "high-complexity"],
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

- The sensor id is the map key, **not** an `id` field inside the entry.
- `command`, `produces`, `items`, and `fields` are required; `group` and `map`
  are optional. The presence of any adapter key (`items`/`fields`/`group`/`map`)
  is what makes a command entry declarative rather than a wrapper script.
- `fields` is the field-name map: each bag field is filled from a dot-path in
  the source (prefix `group.` to read the outer entry).
- `map` rewrites the raw `smell` value to a canonical key; the raw key is
  kept in `details.source`. Omit for identity passthrough.
- Anything the adapter cannot express falls back to a wrapper script.

### `dependsOn` (multi sensors)

A wrapper or declarative entry may add `dependsOn: ["<smell>", ...]` to consume
other sensors' smells (the same `dependsOn` from the [Contract](#contract)).
The runner orders producers before the multi sensor and hands their issues to
it in `ctx.deps`. `use` entries inherit `dependsOn` from the factory and must
not set it themselves.

## Sensors and smells are a pair

A declared sensor does not run on its own. Two gates govern it:

- **A sensor only runs** when at least one smell it `produces` has an active
  rule — a `smells.<smell>` entry that is not disabled and resolves to a
  non-empty in-scope file set. Disabling or empty-scoping every smell a sensor
  produces suppresses the whole sensor.
- **A finding is only coached** when its smell is routed (has a `smells.<smell>`
  entry or a catalogue prompt); otherwise it lands in the uncoached bucket.

So a **custom** sensor must be declared as a pair: its `sensors.<id>` entry
**and** a matching `smells.<smell>` entry. A custom smell entry carries
`source: "custom"` and therefore requires an explicit `id`, plus `severity`,
and optionally `title`/`description`:

```jsonc
{
  "sensors": {
    "marker": { "command": "node sensor.js ${files}", "produces": ["custom-marker"] }
  },
  "smells": {
    "custom-marker": {
      "id": "custom-marker",
      "source": "custom",
      "severity": "enforced",
      "title": "Custom marker",
      "description": "flagged by the project's own sensor"
    }
  }
}
```

## Authoritative semantics and the language presets

When `sensors` is present it is **authoritative**: it replaces the preset
entirely (no merge). Removing a built-in is just deleting its entry; adding one
means starting from the full preset block below and editing it.

When `sensors` is **absent**, the language preset is used and a deprecation
warning is emitted on stderr — this implicit fallback is removed in the 1.0.0
release, so declare `sensors` explicitly.

Copy-pasteable default blocks per language:

**TypeScript/JavaScript**

```jsonc
{
  "sensors": {
    "eslint":           { "use": "eslint" },
    "comment":          { "use": "comment" },
    "jscpd":            { "use": "jscpd" },
    "knip":             { "use": "knip" },
    "needs-extraction": { "use": "needs-extraction" }
  }
}
```

**Python**

```jsonc
{
  "sensors": {
    "ruff":             { "use": "ruff" },
    "jscpd":            { "use": "jscpd" },
    "deptry":           { "use": "deptry" },
    "line-count":       { "use": "line-count" },
    "needs-extraction": { "use": "needs-extraction" }
  }
}
```

Each built-in sensor owns its raw → smell translation (see
[smell-vocabulary.md](smell-vocabulary.md)).

`init` writes the default block automatically: a freshly scaffolded config
carries an explicit `sensors` map for the detected language (#51). Planned
follow-up: per-sensor params will move onto the entries (#50).

## Custom languages and `files`

`language` accepts any string. The two built-ins (`typescript`, `python`) get a
preset and default file-discovery globs out of the box. Any other value relies
on `files` (discovery globs) plus a `sensors` map — there is no preset to fall
back to. If a non-built-in `language` is set without `files`, no source files
are discovered and a warning is emitted on stderr.

```jsonc
{
  "language": "go",
  "files": ["**/*.go"],
  "sensors": {
    "marker": { "command": "node sensor.js ${files}", "produces": ["custom-go-smell"] }
  },
  "smells": {
    "custom-go-smell": {
      "id": "custom-go-smell",
      "source": "custom",
      "severity": "enforced",
      "title": "Custom Go smell",
      "description": "flagged by the project's own Go sensor"
    }
  }
}
```

## More sensor wrappers (long term)

Limit, fail-fast, change-set, and cache are sensors that wrap other sensors,
expressible against this contract without changing it. Added as needed.
