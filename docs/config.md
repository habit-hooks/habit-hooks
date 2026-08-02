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
| `transformers` | An ordered list of transformers applied to the concatenated findings of the whole run, in order. **Defaults to `["snooze"]`**, so a checked-in snooze index takes effect with no wiring; the core ships that transformer, so the default resolves whatever `plugins` names. Naming the key replaces the list wholesale — write `transformers = []` to drop snooze, or name `snooze-until-changed` for the ratchet variant below. |
| `files`        | Discovery globs (pathspec / gitignore) — what this project counts as source, in **every** scope mode. Defaults to what the loaded plugins declare (below); naming it replaces those wholesale. |
| `[scope]`      | Git-scoping defaults for a run with no scope flag. |

```toml
plugins = ["generic", "python"]
transformers = ["snooze"]
files = ["**/*.py"]
```

### The transformers the core ships

Plugins may ship their own; these two come with the core, so either name
resolves whatever `plugins` says ([habit-snooze.spec.md](habit-snooze.spec.md)).
They read the same `.habit-hooks/snooze.json` index and differ only in how long
an exemption lasts, so list **one** of them.

| Transformer | An issue whose `key` is in the index is dropped… |
|-------------|--------------------------------------------------|
| `snooze` | …always. The exemption lasts until someone takes the key out of the index. **The default.** |
| `snooze-until-changed` | …only while its file is unchanged since this branch left `[scope] branchBase` (measured from the merge base, so someone else's later work on the base ref lapses nothing). Commit a change to that file, or just edit it in the working tree, and its issues come back — the index is a ratchet, not an exemption list. Opt in by naming it. A path git cannot place counts as unchanged; a `branchBase` a real repository cannot resolve **fails the run** rather than silently exempting everything. |

```toml
transformers = ["snooze-until-changed"]
```

Both read an index of keys the runner has already **anchored**: a sensor's paths
are re-expressed relative to the project before any key reaches the index
([sensor-interface.spec.md](sensor-interface.spec.md)), so a key recorded on one
machine matches on every other. Nothing in a project's config has to arrange
that, and a sensor a project writes itself gets it without knowing it exists.

### Installing the plugins you list

`plugins` only **selects** among plugins that are installed; each name must
resolve to an installed package (or a `.habit-hooks/<plugin>/` override). The
first-party plugins are exposed as **install extras** on `habit-hooks`, so one
install pulls the core plus the plugin packages you want:

```bash
pip install "habit-hooks[python]"            # core + habit-hooks-python
pip install "habit-hooks[python,typescript]" # several at once
```

The `generic` plugin ships as part of the core install; each extra (`python`,
`typescript`, `php`) installs the matching
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

`files` uses pathspec (gitignore) matching, which has **no brace expansion**.
Write a list of patterns, one per extension — never a `{…}` alternation:

```toml
files = ["**/*.ts", "**/*.tsx"] # ✅
# files = "**/*.{ts,tsx}"        ❌ matched literally, never expanded
```

### `files` describes every mode, not just `--all`

`files` is applied wherever the scope came from — `--all`, `--file`, and every
git-derived mode ([habit-sensors.spec.md](habit-sensors.spec.md)). A branch that
bumps a lockfile is therefore not scored on it, and a run scoped to a branch is
scoped to that branch's *source* changes. Paths the work tree no longer has are
dropped as well: a file deleted on the branch has no smells left to find.

### `files` defaults to what the plugins declare

A plugin states what its sensors consider source in its own `config.toml`
([authoring-plugins.spec.md](authoring-plugins.spec.md)). With no project
`files`, the run scans the union of every active plugin's globs, in `plugins`
order — so a project running `python` and `typescript` scans both languages
without configuring anything:

```toml
# habit_hooks_python/config.toml   ->  files = ["**/*.py"]
# habit_hooks_typescript/config.toml -> files = ["**/*.ts", "**/*.tsx"]

plugins = ["python", "typescript"]   # scans **/*.py, **/*.ts, **/*.tsx
```

Two rules cover the rest:

- **The project's own `files` is authoritative.** Naming it replaces the plugins'
  defaults wholesale rather than adding to them, the same way naming
  `transformers` does. Order is kept as written, so a later pattern can negate an
  earlier one.
- **A plugin that declares no `files` states no opinion, not "everything".**
  `generic` declares none, so a project whose plugins all stay silent scans the
  whole tree — the behaviour a bare install has always had.

### `[scope]`

When a run is invoked with no explicit scope flag (`--all`, `--branch`, …), the
scope is derived from `[scope]`. The scope flags themselves live in
[habit-sensors.spec.md](habit-sensors.spec.md).

| Field               | Meaning |
|---------------------|---------|
| `changedOnly`       | Restrict the default run to uncommitted work: staged and unstaged edits, plus untracked (non-ignored) new files. |
| `autoBranchOffMain` | When not on `mainBranch`, default to diffing against `branchBase`. |
| `branchBase`        | Base ref for branch-relative scoping (used by `--branch` and `autoBranchOffMain`). It must exist in the checkout: a ref a real repository cannot resolve **fails the run**, rather than scoping it to nothing and reporting clean. Scoping starts at the merge base of this ref and `HEAD`, so work landed on the base after you branched is never scanned as yours. |
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

The full spec for a sensor lives in the plugin's `sensors/<name>.toml`
([sensor-interface.spec.md](sensor-interface.spec.md)); the `[sensors.<name>]`
block in a project config only *overrides* a sensor the plugin already defines.
Each key replaces the sensor spec's default wholesale — to change anything a key
below does not cover, drop a whole `.habit-hooks/<plugin>/sensors/<name>.toml`
replacement instead.

| Field      | Meaning |
|------------|---------|
| `disabled` | Drop the sensor entirely. |
| `files`    | Narrow the run's scope to these globs for this sensor alone (list form — no brace expansion). |
| `args`     | Replace the sensor's default CLI args, expanded into its command via `${args}`. |

```toml
# Turn off a sensor the plugin ships.
[sensors.knip]
disabled = true

# Narrow the generic line-count sensor to a subset of the tree.
[sensors.line-count]
files = ["src/**/*.py"]
```

`files` does not widen a run: it selects a subset of the files the run's scope
already picked ([scope]/[files] and the scope flags), so a sensor still never
sees a path the run as a whole was not measuring.

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
Declare it under `[smells.<name>]` with a `severity` so it routes the way you want
instead of escalating with the generic uncoached prompt:

```toml
[smells.custom-marker]
severity = "enforced"
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
```
