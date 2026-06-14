# Sensors

A sensor **finds smells**. It runs a tool (or scans the AST directly) and
appends `Issue`s to the bag, translating its tool's raw rule IDs into
canonical [smell keys](smell-vocabulary.md).

## Contract

```ts
interface Sensor {
  id: string;
  run(files: string[], cwd: string): Promise<Issue[]>;
}

interface Issue {
  smell: string;          // canonical key (kebab-case) — the routing key
  file: string;
  line: number;
  column?: number;
  message: string;
  source: string;         // provenance, e.g. "eslint:max-params"
  details?: Record<string, unknown>;
}
```

Sensors are **additive** and **deterministic**: each appends to the bag, and
detection is mechanical — no judgement. Push every rule as far left as
possible; only what truly needs judgement should reach the AI.

A sensor must never throw on tool spawn/timeout failure. Failures surface as
a stderr notice and zero issues, never a lost run. (Today's `src/wrap/`
shell semantics already enforce this.)

## Built-in sensors

Shipped for TypeScript/JavaScript, enabled by default. Each owns its raw →
smell translation table (see the migration table in
[smell-vocabulary.md](smell-vocabulary.md)).

| Sensor | Tool | Smells produced |
|---|---|---|
| `eslint` | ESLint | size/complexity/correctness/TS smells, `parse-error` |
| `knip` | knip | `unused-file`, `unused-export`, `unused-dependency`, `unused-class-member` |
| `jscpd` | jscpd | `duplicated-code` |
| `comment` | ts-morph AST scan | `non-essential-comment` |

## External command sensor

The extension point for other languages. No code required — declare it in
config:

```jsonc
{
  "sensors": {
    "ruff": {
      "type": "command",
      "command": "ruff check --output-format=json ${files}",
      "map": {
        "R0913": "too-many-parameters",
        "C901":  "high-complexity",
        "F841":  "unused-variable"
      }
    }
  }
}
```

- `command` — the shell command to run. `${files}` expands to the scoped
  file list. The command **must print bag JSON to stdout**:
  `{ "issues": [ { "smell": <raw tool key>, "file", "line", "message", ... } ] }`.
  (The user wraps the tool's native output into this shape; thin tools that
  already emit it need no wrapper.)
- `map` — `rawKey → smellKey`. Applied to each issue's `smell` field after
  the command runs, rewriting raw tool keys into canonical smell keys. The
  raw key is preserved in `source`. Omit `map` for identity passthrough
  (when the wrapper already emits canonical keys).

Keeping the translation in declarative config (rather than in the wrapper
script) keeps the project's smell vocabulary visible in one place.
*(Agent decision — flag if you'd rather the wrapper emit canonical keys
directly.)*

## Composability (future)

Llewellyn's catalogue of sensor wrappers — multi, limit, fail-fast,
change-set, cache, external — are all expressible against this contract as
sensors that wrap other sensors. We implement them as needed; the contract
is designed to allow them without change.

The **composite sensor** is the long-term home for combination smells: a
sensor that subscribes to other sensors' issues and emits a derived smell
(e.g. `oversized-file` + `duplicated-code` in one file → `needs-extraction`).
This keeps the mapper a pure single-smell function. Deferred for now.
