# Authoring plugins

This is the end-to-end manual for building a plugin: a small installable package
holding a sensor that finds a smell, the adapter trick for wrapping an existing
linter, a transformer that reshapes findings, and a guide that coaches the fix.
It runs top to bottom — each step builds on the last.

It assumes you already know the moving parts: what a plugin is and how resolution
works ([architecture.md](architecture.md)), the exact finding shape every stage
passes ([sensor-interface.spec.md](sensor-interface.spec.md)), and the config
format ([config.md](config.md)). Read those first; this manual links back rather
than re-explaining them.

```bash
habit-sensors() { ../../habit-sensors "$@"; }
habit-mapper()  { ../../habit-mapper; }
```

## 1. A plugin is an installable package

A plugin is a self-contained **Python package** — no core code. You build it,
publish it, and a consumer `pip install`s it; the core finds it at run time
through a packaging **entry point**, never by looking inside this repo. A plugin
does not need to live in the habit-hooks repo at all.

The package follows one naming convention: the **distribution** is
`habit-hooks-<name>` (what you `pip install`) and the **import package** is
`habit_hooks_<name>` (where the files live). The sensors, guides, transformers,
and `config.toml` ship as **package data** inside that import package:

```
habit-hooks-<name>/
  pyproject.toml                       # declares the dist + the entry point
  src/habit_hooks_<name>/
    __init__.py                        # may be empty; must import cleanly
    config.toml                        # what this plugin contributes, and the language it speaks
    sensors/                           # how it finds smells       — package data
    transformers/                      # how it reshapes findings  — package data
    guides/                            # how it coaches each fix    — package data
```

`pyproject.toml` registers the plugin under the `habit_hooks.plugins`
entry-point group, mapping the **plugin name** (what a project lists in its
`plugins`) to the **import package** whose bundled files are the plugin's
defaults:

```toml
# habit-hooks-lua/pyproject.toml
[project]
name = "habit-hooks-lua"
version = "0.0.0"
requires-python = ">=3.11"

[project.entry-points."habit_hooks.plugins"]
lua = "habit_hooks_lua"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/habit_hooks_lua"]
```

`config.toml` is where the plugin *declares the language it speaks*. The runner
stamps that `language` onto every finding the plugin's sensors emit, so the
mapper can prefer this plugin's guide for that language. A plugin is not a
language — several plugins may declare the same one — and `generic` declares
none. The concept is in [architecture.md](architecture.md); the field-by-field
format is in [config.md](config.md).

```toml
# src/habit_hooks_lua/config.toml
language = "lua"
files = ["**/*.lua"]            # what this plugin's sensors scan by default
sensors = ["todo"]             # the sensors this plugin enables, in order
```

A consumer who installs the package and lists `lua` in `plugins` gets these
defaults; to *tune* them per project they drop overriding files under
`.habit-hooks/lua/`, which win over the installed package data
([architecture.md](architecture.md)). Everything below adds package-data files
into this bundle; §6 builds, installs, and runs the finished package.

## 2. Write a sensor

A sensor *senses*: it runs a tool or a script over the files in scope and prints
a findings array. It takes no findings as input. Each sensor is one
`sensors/<name>.toml` — both the static descriptor and the recipe for running it.

```toml
# src/habit_hooks_lua/sensors/todo.toml
command = "grep -Hrn TODO ${files} | jq -Rn '<transform>'"   # required
files = ["**/*.lua"]                                        # optional; overrides the plugin globs
```

| Field | Required | Meaning |
|-------|----------|---------|
| `command` | yes | Shell command to run; it must print a JSON array of findings. `${files}` expands to the scoped file list; `${dir}` to this spec's directory (for bundled scripts). |
| `language` | no | Language stamped on every finding this sensor emits. Usually inherited from the plugin's `config.toml` rather than set here. |
| `files` | no | Per-sensor discovery globs, overriding the plugin's. |

Whatever the command prints is taken verbatim as the sensor's findings; a clean
run prints `[]`, never nothing ([sensor-interface.spec.md](sensor-interface.spec.md)).

Every finding has the shape `{smell, language?, details, issues:[{key, details}]}`:
one finding per smell, one `issues` entry per occurrence, the issue `key` being
what snoozing acts on (default: the file path).

### A native sensor: grep for TODO, shaped with jq

The command pipes `grep` through `jq` to emit one `warning-comment` finding whose
`issues` lists each TODO. Run the pipeline directly against a sample file to see
exactly what the sensor emits. The `-H` flag forces grep to print the `file:`
prefix even when the scope is a single file — GNU grep omits it otherwise, which
would break the capture on Linux.

📄src/util.lua
```lua
local function add(a, b)
  -- TODO: validate inputs
  return a + b
end
```

```bash
grep -Hrn TODO src | jq -Rn '[
  inputs | capture("(?<file>[^:]+):(?<line>[0-9]+):(?<text>.*)")
  | { key: .file,
      details: { file: .file,
                 line: (.line | tonumber),
                 message: (.text | gsub("^\\s*--\\s*"; "")) } }
] | { smell: "warning-comment", details: {}, issues: . }'
```

🖥️ ✅
```text
{
  "smell": "warning-comment",
  "details": {},
  "issues": [
    {
      "key": "src/util.lua",
      "details": {
        "file": "src/util.lua",
        "line": 2,
        "message": "TODO: validate inputs"
      }
    }
  ]
}
```

A sensor emits an *array* of findings; here it is a single one. Anything `jq`
cannot express becomes a script — `command = "python ${dir}/todo.py ${files}"` —
as long as it prints the same array.

## 3. The adapter technique

Most linters already emit JSON. An **adapter sensor** is just a native sensor
whose `command` pipes that JSON through `jq` to reshape it into findings — there
is no separate mapping language, the transform lives in the command.

```toml
# src/habit_hooks_python/sensors/ruff.toml
command = "ruff check --output-format json ${files} | jq '<transform>'"
```

The two examples below are pure `jq`, so they run today with no habit-hooks code.
Each maps a tool's flat or nested output into **one finding per smell**, grouping
occurrences into `issues` with `key` = the file.

### Ruff's flat list maps with one jq expression

Ruff prints a flat array of violations. Group them by smell, then by file into
`issues`.

⌨️
```json
[
  {
    "code": "PLR0913",
    "filename": "src/billing.py",
    "location": { "row": 2, "column": 1 },
    "message": "Too many arguments in function definition"
  }
]
```

```bash
jq 'map(. + {smell: ({"PLR0913": "too-many-parameters"}[.code])})
  | group_by(.smell)
  | map({
      smell: .[0].smell,
      details: {},
      issues: map({
        key: .filename,
        details: {
          file: .filename,
          line: .location.row,
          column: .location.column,
          message: .message,
          source: ("ruff:" + .code)
        }
      })
    })'
```

🖥️ ✅
```text
[
  {
    "smell": "too-many-parameters",
    "details": {},
    "issues": [
      {
        "key": "src/billing.py",
        "details": {
          "file": "src/billing.py",
          "line": 2,
          "column": 1,
          "message": "Too many arguments in function definition",
          "source": "ruff:PLR0913"
        }
      }
    ]
  }
]
```

### ESLint's per-file messages flatten with `.messages[]`

ESLint nests messages under each file. Flatten with `.messages[]`, carrying the
`filePath` down, then group the same way.

⌨️
```json
[
  {
    "filePath": "src/billing.ts",
    "messages": [
      {
        "ruleId": "max-params",
        "line": 2,
        "column": 22,
        "message": "Too many parameters (4)"
      }
    ]
  }
]
```

```bash
jq '[.[] | .filePath as $file | .messages[] | {
      smell: {"max-params": "too-many-parameters"}[.ruleId],
      file: $file, line: .line, column: .column,
      message: .message, ruleId: .ruleId
    }]
  | group_by(.smell)
  | map({
      smell: .[0].smell,
      details: {},
      issues: map({
        key: .file,
        details: {
          file: .file,
          line: .line,
          column: .column,
          message: .message,
          source: ("eslint:" + .ruleId)
        }
      })
    })'
```

🖥️ ✅
```text
[
  {
    "smell": "too-many-parameters",
    "details": {},
    "issues": [
      {
        "key": "src/billing.ts",
        "details": {
          "file": "src/billing.ts",
          "line": 2,
          "column": 22,
          "message": "Too many parameters (4)",
          "source": "eslint:max-params"
        }
      }
    ]
  }
]
```

## 4. Write a transformer

A transformer *transforms*: it receives the whole findings array on **stdin** and
prints a new one on **stdout**. It may add, drop, or rewrite findings. Each is one
`transformers/<name>.toml` with a `command`, listed in the plugin's
`config.toml`; the runner pipes the concatenated sensor output through the
plugin's transformers in order ([architecture.md](architecture.md)).

```toml
# src/habit_hooks_lua/transformers/tag-fixme.toml
command = "jq '<transform>'"
```

> **A transformer must pass through every finding it does not handle.**

That single rule is what lets transformers compose freely. The transform below
annotates `warning-comment` findings and leaves everything else untouched — note
the `else .` branch carrying unrelated findings through verbatim.

⌨️
```json
[
  { "smell": "warning-comment", "details": {},
    "issues": [{ "key": "src/util.lua", "details": { "file": "src/util.lua", "line": 2, "message": "TODO: validate inputs" } }] },
  { "smell": "too-many-parameters", "details": {},
    "issues": [{ "key": "src/billing.py", "details": { "file": "src/billing.py", "line": 7 } }] }
]
```

```bash
jq 'map(if .smell == "warning-comment"
        then .details += {reviewed: true}
        else . end)'
```

🖥️ ✅
```text
[
  {
    "smell": "warning-comment",
    "details": {
      "reviewed": true
    },
    "issues": [
      {
        "key": "src/util.lua",
        "details": {
          "file": "src/util.lua",
          "line": 2,
          "message": "TODO: validate inputs"
        }
      }
    ]
  },
  {
    "smell": "too-many-parameters",
    "details": {},
    "issues": [
      {
        "key": "src/billing.py",
        "details": {
          "file": "src/billing.py",
          "line": 7
        }
      }
    ]
  }
]
```

To *replace* a finding, emit the replacement and drop the original; to *add*,
append. There is no dependency graph and no special mode — order between
transformers is the only thing that matters.

## 5. Write a guide

A guide coaches the fix for **one smell**. It lives in `guides/` and resolves
across the override chain; a finding's `language` selects this plugin's guide
before the generic one ([architecture.md](architecture.md)).

### `guides/<smell>.md` — a Jinja2 template

The mapper renders `guides/<smell>.md` once against the whole finding: read
smell-level facts straight off `details`, and loop `issues` for the
per-occurrence ones, reading each occurrence's own `details`.

```markdown
<!-- src/habit_hooks_lua/guides/warning-comment.md -->
{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }} — {{ v.details.message }}
{% endfor %}
Resolve or remove these markers before merging.
```

`smell` and `language` are in scope too, and `details.<field>` reads a
smell-level fact (a threshold, say). A plain markdown file with no interpolation
is the degenerate case; templates may `{% include %}` partials from the same
override chain.

### `guides/<smell>.<ext>` — a script run by a runner

A guide can instead be a script in any language. The core does **not** run it
directly: it looks up the command registered for `<ext>` under `[runners]` and
runs `<command> guides/<smell>.<ext>` with the finding on stdin. The script's
stdout/stderr is shown to the agent and its exit code drives pass/fail (non-zero
contributes exit 1 for an `enforced` smell; a spawn/timeout failure always
blocks).

`.md` is always rendered; **every other extension needs a runner, or nothing
executes**. A plugin therefore ships its **own** `[runners]` in its
`config.toml`, so its language-specific fixers run by default — core registers
only the `.md` renderer.

```toml
# src/habit_hooks_python/config.toml
language = "python"
files = ["**/*.py"]

[runners]
py = "python"                  # guides/<smell>.py -> python guides/<smell>.py
```

Author a guide only where the language needs its own wording; otherwise the smell
falls back to the generic guide, or the `uncoached.md` default. Keep prompts short
and outcome-focused — use the `habit-hooks-prompting` skill's ROSE pattern.

## 6. Build it, install it, run it

Now assemble the `habit-hooks-lua` package from the pieces above, install it the
way a consumer would, and run the whole pipeline against a Lua file. A plugin
ships as a wheel, so a sensor must print a JSON **array** — here the `jq` from §2
wrapped in `[ … ]` so its single object becomes a one-element array.

📄habit-hooks-lua/pyproject.toml
```toml
[project]
name = "habit-hooks-lua"
version = "0.0.0"
requires-python = ">=3.11"

[project.entry-points."habit_hooks.plugins"]
lua = "habit_hooks_lua"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/habit_hooks_lua"]
```

📄habit-hooks-lua/src/habit_hooks_lua/__init__.py
```python
```

📄habit-hooks-lua/src/habit_hooks_lua/config.toml
```toml
language = "lua"
files = ["**/*.lua"]
sensors = ["todo"]
```

📄habit-hooks-lua/src/habit_hooks_lua/sensors/todo.toml
```toml
command = "grep -Hrn TODO ${files} | jq -Rn '[[inputs | capture(\"(?<file>[^:]+):(?<line>[0-9]+):(?<text>.*)\") | { key: .file, details: { file: .file, line: (.line | tonumber), message: (.text | gsub(\"^\\\\s*--\\\\s*\"; \"\")) } }] | { smell: \"warning-comment\", details: {}, issues: . }]'"
```

📄habit-hooks-lua/src/habit_hooks_lua/guides/warning-comment.md
```markdown
{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }} — {{ v.details.message }}
{% endfor %}
Resolve or remove these markers before merging.
```

Build the wheel and install it into a local target dir, then point Python at it —
exactly what `pip install habit-hooks-lua` would do, minus a registry. The core
discovers the plugin through its entry point, no path into this package required.

```bash
uv pip install --quiet --target vendor ./habit-hooks-lua
```

✏️PYTHONPATH
```text
vendor
```

The project turns the installed plugin on by listing it; `files` scopes the run
to Lua sources so the sensor sees only them.

📄.habit-hooks/config.toml
```toml
plugins = ["lua"]
files = ["**/*.lua"]
```

📄src/util.lua
```lua
local function add(a, b)
  -- TODO: validate inputs
  return a + b
end
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ✅
```text
── warning-comment (1 issue) ──

src/util.lua:2 — TODO: validate inputs

Resolve or remove these markers before merging.
```

A Lua file with a `TODO` now surfaces `warning-comment`, routed to your guide —
from an installed package the core never had to be told the location of. What
each stage guarantees is pinned in
[sensor-interface.spec.md](sensor-interface.spec.md),
[habit-sensors.spec.md](habit-sensors.spec.md), and
[habit-mapper.spec.md](habit-mapper.spec.md).
