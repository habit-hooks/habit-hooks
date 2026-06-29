# Config

All configuration is TOML. There are **two kinds of file, the same shape**:

- **Plugin defaults** — `config.toml` shipped as package data inside each plugin's
  installed package (`habit_hooks_<plugin>/config.toml`). They state what the
  plugin contributes and the language it speaks. Plugins are separate installable
  packages, discovered at run time through the `habit_hooks.plugins` entry-point
  group ([architecture.md](architecture.md)).
- **Project overrides** — `.habit-hooks/config.toml` in the consumer repo. It
  tunes the run and the plugins, holding only what differs from the defaults.

The two are merged in resolution order — generic defaults, then each language
plugin's defaults, then the project — with the **project last and winning**.
Override, never overwrite: the resolution and override chain (and how plugins are
discovered and selected) is owned by [architecture.md](architecture.md); this
document is only the field reference for the format that drives it.

Every field is optional. An empty `.habit-hooks/config.toml` is valid — it means
"use the plugin defaults".

## One file, two readers

There is no physical split between the two stages of the pipeline. The single
config file is read by both, each picking out the keys it cares about:

| Stage | Reads |
|-------|-------|
| **`habit-sensors`** (the runner) | `plugins`, `transformers`, `files`, `[scope]`, `[sensors.*]` |
| **`habit-mapper`** (the router)  | `[smells.*]`, `[runners]` |

## Root keys

These live at the top level of the **project** `config.toml`.

| Key            | Meaning |
|----------------|---------|
| `plugins`      | An **ordered** list of plugins to activate, **selecting among the installed plugin packages** by name. The order is a priority: it is the order sensors run and the order the mapper looks up guides (earlier wins, `generic` last). A listed plugin that is neither installed nor overridden under `.habit-hooks/<plugin>/` fails with an error naming its `pip install habit-hooks-<plugin>` command. `generic` is listed explicitly like any other plugin, so a project can drop it. |
| `transformers` | An ordered list of transformers applied to the concatenated findings of the whole run, in order. |
| `files`        | Discovery globs (pathspec / gitwildmatch). Defaults come from the loaded plugins. |
| `[scope]`      | Git-scoping defaults for a run with no scope flag. |

```toml
plugins = ["generic", "python"]
transformers = ["snooze"]
files = ["**/*.py"]
```

### Installing the plugins you list

`plugins` only **selects** among plugins that are installed; each name must
resolve to an installed package (or a `.habit-hooks/<plugin>/` override). The
first-party plugins are exposed as **install extras** on `habit-hooks`, so one
install pulls the core plus the plugin packages you want:

```bash
pip install "habit-hooks[python]"            # core + habit-hooks-python
pip install "habit-hooks[python,typescript]" # several at once
```

Each extra (`generic`, `python`, `typescript`, `php`) installs the matching
`habit-hooks-<name>` distribution; a third-party plugin is just a package you
`pip install habit-hooks-<name>` directly. The core then finds every installed
plugin through its entry point — nothing else is configured for discovery.

### Overriding an installed plugin

A project tunes any installed plugin by dropping replacement files under
`.habit-hooks/<plugin>/`, which mirror the package's data layout and win over it:

```
.habit-hooks/<plugin>/<file>   →   installed habit_hooks_<plugin> package data/<file>
```

So `.habit-hooks/python/sensors/ruff.toml` replaces only that one sensor, leaving
the rest of the installed `python` plugin intact. `config.toml` merges field by
field the same way (project last); every other file is whole-file replacement.
This is the mechanism owned by [architecture.md](architecture.md).

### Pinning plugins at run time

Because plugins are ordinary packages, pin them like any dependency — the run is
reproducible only to the extent the installed plugin versions are. Recommended:

- Install the core and its plugins together as extras
  (`habit-hooks[python,typescript]`) and lock them in your project's lockfile, so
  every machine and CI run resolves the same plugin versions.
- Prefer a per-project virtualenv over a global tool install when the project
  relies on plugin behaviour, so a plugin upgrade is a deliberate, reviewable
  lockfile change rather than an ambient one.
- `habit-sensors` already prepends `node_modules/.bin` and `.venv/bin` to `PATH`
  ([habit-sensors.spec.md](habit-sensors.spec.md)), so a plugin's sensor commands
  pick up the project-local tools (`ruff`, `eslint`, …) those plugins shell out to.

### `files` globs have no brace expansion

`files` uses pathspec (gitwildmatch) matching, which has **no brace expansion**.
Write a list of patterns, one per extension — never a `{…}` alternation:

```toml
files = ["**/*.ts", "**/*.tsx"]   # ✅
# files = "**/*.{ts,tsx}"          ❌ matched literally, never expanded
```

### `[scope]`

When a run is invoked with no explicit scope flag (`--all`, `--branch`, …), the
scope is derived from `[scope]`. The scope flags themselves live in
[habit-sensors.spec.md](habit-sensors.spec.md).

| Field               | Meaning |
|---------------------|---------|
| `changedOnly`       | Restrict the default run to uncommitted (git-changed) files. |
| `autoBranchOffMain` | When not on `mainBranch`, default to diffing against `branchBase`. |
| `branchBase`        | Base ref for branch-relative scoping (used by `--branch` and `autoBranchOffMain`). |
| `mainBranch`        | The branch name on which `autoBranchOffMain` does *not* kick in. |

```toml
[scope]
changedOnly = false
autoBranchOffMain = true
branchBase = "main"
mainBranch = "main"
```

## Plugin-node keys

A plugin's own `config.toml` (shipped as package data in
`habit_hooks_<plugin>/config.toml`, or shadowed by a
`.habit-hooks/<plugin>/config.toml` override) uses a different, smaller set of
root keys — it describes the plugin, not the whole run:

| Key            | Meaning |
|----------------|---------|
| `language`     | The language this plugin **declares**. A plugin is not a language: its name need not match, several plugins can declare the same language, and the runner stamps this onto the plugin's findings. `generic` declares none. |
| `sensors`      | An ordered list of the sensor names the plugin runs. |
| `transformers` | An ordered list of the plugin's own transformers, applied to its sensors' concatenated findings before the result joins the larger run. |

```toml
# habit_hooks_python/config.toml
language = "python"
sensors = ["ruff", "deptry", "line-count"]
transformers = []
```

## `[sensors.<name>]`

A sensor spec is just a **`command`** plus an optional **`language`** and
**`files`** — that is the whole sensor interface
([sensor-interface.spec.md](sensor-interface.spec.md)). The full spec for a
sensor lives in the plugin's `sensors/<name>.toml`; the `[sensors.<name>]` block
in a config only *overrides* a sensor the plugin already defines.

| Field      | Meaning |
|------------|---------|
| `disabled` | Drop the sensor entirely. |
| `files`    | Override the sensor's file globs (list form — no brace expansion). |
| `command`  | Override the sensor's command. |
| `language` | Override the language stamped on the sensor's findings. |

```toml
# Turn off a sensor the plugin ships.
[sensors.knip]
disabled = true

# Narrow a sensor to a subset of the tree.
[sensors.line-count]
files = ["src/**/*.py"]
```

## `[smells.<name>]`

Per-smell routing overrides, keyed by smell. A smell with no override uses the
catalogue default ([smell-vocabulary.md](smell-vocabulary.md)).

| Field                 | Meaning |
|-----------------------|---------|
| `severity`            | `enforced` (fails the run, exit 1) or `suggested` (coaches only, exit 0). |
| `disabled`            | Drop the smell — neither coached nor counted. |
| `guide`               | Use a named guide file instead of `<smell>.md`. |

```toml
[smells.duplicated-code]
severity = "suggested"

[smells.redundant-type-annotation]
guide = "style-nit.md"
```

## `[runners]`

The mapper renders each smell's guide. A `.md` guide is always rendered as a
template and needs no runner. Any other extension needs one: `[runners]` maps a
guide-file extension to the command that runs it, and the mapper invokes
`<command> guides/<smell>.<ext>` with the finding on stdin. No non-`.md` guide
executes unless its extension is opted in here.

```toml
[runners]
py = "python"
js = "node"
```

`[runners]` resolves through the same override chain as everything else, so a
**plugin can ship its own `[runners]`** — a language plugin can register the
fixer command for its guides' extension and run its own language-specific fixers
by default, without the project configuring anything.

## Custom smells

A project (or plugin) sensor may emit a smell that is not in the catalogue.
Declare it under `[smells.<name>]` with a `title` and `severity` so it routes the
way you want instead of escalating with the generic uncoached prompt:

```toml
[smells.custom-marker]
severity = "enforced"
title = "Custom marker"
description = "flagged by the project's own sensor"
```

Pair the declaration with a sensor that emits the smell (a `sensors/<name>.toml`
whose command produces findings with that `smell` key) and a matching
`guides/custom-marker.md`.

## A worked example

A single `.habit-hooks/config.toml` for a TypeScript project — every key below
is optional:

```toml
# .habit-hooks/config.toml — all optional; an empty file means "plugin defaults".

plugins = ["generic", "typescript"]              # ordered = lookup priority; drop "generic" to disable it
transformers = ["snooze"]                         # applied to the whole run's findings, in order
files = ["**/*.ts", "**/*.tsx", "**/*.js"]        # list form — pathspec has no brace expansion

[scope]
changedOnly = false
autoBranchOffMain = true
branchBase = "main"
mainBranch = "main"

# Run non-.md guides: guide extension -> command. (.md needs none.)
[runners]
py = "python"

# Turn off a sensor the plugin ships.
[sensors.knip]
disabled = true

# Narrow the generic line-count sensor to source files.
[sensors.line-count]
files = ["src/**/*.ts"]

# Demote a smell from blocking to advisory.
[smells.duplicated-code]
severity = "suggested"

# Reuse a shared guide instead of redundant-type-annotation.md.
[smells.redundant-type-annotation]
guide = "style-nit.md"

# A project-local custom smell + the sensor that emits it (paired with
# .habit-hooks/typescript/sensors/marker.toml and guides/custom-marker.md).
[smells.custom-marker]
severity = "enforced"
title = "Custom marker"
description = "flagged by the project's own sensor"
```
