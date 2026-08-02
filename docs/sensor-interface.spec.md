# The finding — the sensor interface

A **finding** is the unit of data Habit Hooks is built around. Every sensor emits
a JSON array of findings; `habit-sensors` concatenates those arrays, transformers
reshape them, and `habit-mapper` consumes them. This document is the contract for
that shape — what a sensor must produce, and therefore what every transformer must
preserve and the mapper can rely on. The big picture is in
[architecture.md](architecture.md).

## The shape

One finding names one smell and lists everywhere it occurs:

```jsonc
{
  "smell": "too-many-parameters",      // routing key — which guide coaches the fix
  "language": "python",                // optional — prefers a language's guide
  "details": { "maxAllowed": 3 },      // facts about the smell itself
  "issues": [                          // one entry per occurrence
    { "key": "src/billing.py",
      "details": { "file": "src/billing.py", "line": 2, "signature": "bill(...)" } }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `smell` | The routing key, in the canonical vocabulary ([smell-vocabulary.md](smell-vocabulary.md)). The mapper picks a guide by this, never by the tool. |
| `language` | Optional. When present, the mapper prefers that language's guide before the generic one. The runner stamps it from the producing plugin (see [habit-sensors.spec.md](habit-sensors.spec.md)); a sensor rarely sets it itself. |
| `details` | A bag of facts about the smell as a whole — e.g. the threshold that was exceeded. The smell decides its shape ([smell-vocabulary.md](smell-vocabulary.md)). |
| `issues` | One entry per occurrence. Each has a `key` and its own `details` bag. |

An issue's `key` is what snoozing acts on, so a sensor chooses it to control what
gets snoozed together; it defaults to the file path, which snoozes a whole file at
once ([habit-snooze.spec.md](habit-snooze.spec.md)). An issue's `details` bag
conventionally carries:

| Field | Meaning |
|-------|---------|
| `file` | path the occurrence was found in |
| `line` / `column` | location within the file |
| `message` | the tool's human-readable message |
| `source` | provenance, e.g. `ruff:PLR0913` |

A guide renders against the whole finding, reading smell-level facts from
`details` and looping over `issues` for the per-occurrence ones — see
[habit-mapper.spec.md](habit-mapper.spec.md).

## Paths are anchored to the project

A sensor reports paths the way its tool does: `ruff`, `eslint` and `ts-morph`
report **absolute** paths, others report them relative to their own scan root.
The runner **anchors** every `details.file` as a sensor's findings enter the run —
resolving it against the project directory and re-expressing it relative to that,
with forward slashes. An issue's `key` is anchored by the same rule, so `./src/a.py`
and an absolute `/…/src/a.py` both come back as `src/a.py`. A key that is not a
path — `deptry` keys by module, `knip` by export name — has nothing to resolve and
comes back exactly as the sensor wrote it.

This is what makes a checked-in snooze index portable: a key recorded on one
machine has to match on a teammate's checkout and in CI, and an absolute path
never does. Anchoring happens in one place for every sensor, bundled or
third-party, so a sensor cannot get the convention wrong by not knowing it exists.

Three things are refused rather than quietly accepted, each as an ordinary sensor
failure — a stderr notice and exit 1 ([habit-sensors.spec.md](habit-sensors.spec.md)):

- **A path the project cannot anchor** — absolute and outside the project
  directory, or relative and escaping it — names the sensor and drops its
  findings. A path that cannot be anchored cannot be keyed either.
- **A key that is one of its own files while covering others too** names the key
  and every file behind it: one snooze would exempt them all, which is the
  over-exemption smell-scoped keys exist to prevent, arriving along the path axis
  instead.
- **Output the contract has no shape for** — an issue that is not an object, a
  `details` that is not one, an `issues` that is not a list — fails by name
  rather than escaping as a traceback. A sensor is somebody else's program.

Anchoring is **lexical**: no path is checked for existing. A sensor may report a
path the scope never handed it — one from a tool's cache, or from its own scan
root — and this boundary reads programs nobody here wrote, so it resolves names
rather than judging what the filesystem holds. (Files a branch deleted never get
this far: the scope drops them before any sensor runs,
[habit-sensors.spec.md](habit-sensors.spec.md).) So a key that matches *none* of
its files — a sensor reporting paths relative to its own scan root — is
indistinguishable from a deliberate grouping key and passes; only the sensor can
fix that one, by reporting paths its project can place.

Every case below runs one sensor whose command prints the findings verbatim.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

### An absolute path is anchored, and its key with it

`ruff` reports an absolute `filename` even when handed a relative path, and the
sensor keys the issue by it. Both come back relative to the project.

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = """
jq -nc --arg file "$PWD/src/billing.py" '[{smell: "too-many-parameters", details: {}, issues: [{key: $file, details: {file: $file, line: 2}}]}]'
"""
```

```bash
habit-sensors --all | jq -c '.[0].issues'
```

🖥️ ✅
```json
[{"key":"src/billing.py","details":{"file":"src/billing.py","line":2}}]
```

### A key that is not a path is left alone

`deptry` keys an unused dependency by module name and points `details.file` at
the manifest that declares it. The file is anchored; the key is not touched,
because it never was that path.

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = """
jq -nc --arg file "$PWD/pyproject.toml" '[{smell: "unused-dependency", details: {}, issues: [{key: "requests", details: {module: "requests", file: $file}}]}]'
"""
```

```bash
habit-sensors --all | jq -c '.[0].issues'
```

🖥️ ✅
```json
[{"key":"requests","details":{"module":"requests","file":"pyproject.toml"}}]
```

### A path outside the project fails the run, naming the sensor

A monorepo tool run from a sibling package can report a file the project has no
way to key. Guessing a key for it would put an entry in the snooze index that
matches nothing anywhere, so the sensor fails like any other broken one. Its
findings drop, leaving only the reserved `incomplete-run` marker a failed run
carries ([habit-sensors.spec.md](habit-sensors.spec.md)).

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = """
jq -nc '[{smell: "oversized-file", details: {}, issues: [{key: "../elsewhere/big.py", details: {file: "../elsewhere/big.py"}}]}]'
"""
```

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
```

🚨
```text
habit-sensors: sensor 'alpha' reported a path outside the project: '../elsewhere/big.py'
```

### One path key for two files fails the run

A sensor with its own scan root can report `index.ts` for a file that really is
`index.ts` and for another that is not. Snoozing that key would exempt both, with
nothing saying so — so the run fails, naming the key and every file behind it.
The findings themselves are sound and still report; the assertion filters out the
reserved `incomplete-run` marker the failed run also appends, to keep the focus on
the kept findings ([habit-sensors.spec.md](habit-sensors.spec.md)).

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = """
jq -nc '[{smell: "duplicated-code", details: {}, issues: [{key: "index.ts", details: {file: "index.ts"}}, {key: "index.ts", details: {file: "ui/src/index.ts"}}]}]'
"""
```

```bash
habit-sensors --all | jq -c '[.[] | select(.smell != "incomplete-run") | .issues[].details.file]'
```

🖥️ ❌ 1
```json
["index.ts","ui/src/index.ts"]
```

🚨
```text
habit-sensors: sensor 'alpha' keys 2 files as 'index.ts' (index.ts, ui/src/index.ts) — snoozing it would exempt them all
```

### Malformed output fails the sensor, not the runner

A sensor is somebody else's program, and the runner reads it at arm's length: a
`details` that is not an object would take the whole run down with a traceback if
this boundary trusted it. It fails by name instead, like any other broken sensor,
its findings dropped so only the reserved `incomplete-run` marker remains
([habit-sensors.spec.md](habit-sensors.spec.md)).

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = """
jq -nc '[{smell: "oversized-file", details: {}, issues: [{key: "src/a.py", details: null}]}]'
"""
```

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
```

🚨
```text
habit-sensors: sensor 'alpha' emitted an issue whose 'details' is not an object
```

### A name key covering several files is the sensor's own grouping

The counterpart to the case above: `knip` keys by export name, and the same name
can be unused in two files. That is the sensor deliberately choosing what gets
snoozed together, not a path standing in for files it isn't — so it passes.

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = """
jq -nc '[{smell: "unused-export", details: {}, issues: [{key: "default", details: {file: "src/a.ts"}}, {key: "default", details: {file: "src/b.ts"}}]}]'
"""
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["default","default"]
```

## A sensor's output is a findings array

Whatever a sensor's command prints is taken as its findings; with a single sensor,
that array is the whole run's output.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "cat ${dir}/alpha.json"
```

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"too-many-parameters","details":{"maxAllowed":3},"issues":[{"key":"src/billing.py","details":{"file":"src/billing.py","line":2,"signature":"bill(...)"}}]}]
```

```bash
habit-sensors --all | jq .
```

🖥️ ✅
```json
[
  {
    "smell": "too-many-parameters",
    "details": {
      "maxAllowed": 3
    },
    "issues": [
      {
        "key": "src/billing.py",
        "details": {
          "file": "src/billing.py",
          "line": 2,
          "signature": "bill(...)"
        }
      }
    ]
  }
]
```

## A clean run emits an empty array

No findings is an empty array, not no output — the mapper depends on always
receiving a valid findings array.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "echo []"
```

```bash
habit-sensors --all | jq .
```

🖥️ ✅
```json
[]
```
