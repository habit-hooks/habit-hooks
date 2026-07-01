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

## A sensor's output is a findings array

Whatever a sensor's command prints is taken as its findings; with a single sensor,
that array is the whole run's output.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
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
