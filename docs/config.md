# Config

All configuration is TOML. There are two kinds of file, same shape:

- **Plugin defaults** — `plugins/<language>/config.toml` and
  `plugins/generic/config.toml`, shipped with the package.
- **Project overrides** — `.habit-hooks/config.toml` in the consumer repo.

They merge in resolution order (generic defaults < language defaults < project),
project last wins. Override, never overwrite — see
[architecture.md](architecture.md).

## Project `config.toml`

```toml
languages = ["typescript"]               # language plugins to load; add more for a multi-language repo
files = ["**/*.{ts,tsx,js,mjs,cjs}"]     # optional; default comes from the loaded plugins

[scope]
changedOnly = false                      # restrict every run to git-changed files
branchBase = "main"                      # base ref for --branch

# Run non-.md guides: file extension -> command.
[runners]
py = "python"                            # guides/<smell>.py -> python guides/<smell>.py

# Turn a sensor off, or override its args/globs. Absent = plugin default.
[sensors.line-count]
disabled = false
args = ["--max", "300"]                  # appended to the sensor's command

# Override a smell's routing. Absent = catalogue default.
[smells.too-many-parameters]
severity = "enforced"                    # enforced (exit 1) | suggested (exit 0)

[smells.duplicated-code]
disabled = true

[smells.redundant-type-annotation]
guide = "style-nit.md"                   # use a different guide file
```

Every field is optional; an empty file is valid (pure plugin defaults).

## Top-level keys

| Key        | Meaning                                                        |
|------------|---------------------------------------------------------------|
| `languages`| Language plugins to load (their sensors run). Built-ins: `typescript`, `python`. |
| `files`    | Discovery globs. Defaults from the loaded plugins.            |
| `scope`    | `changedOnly` and `branchBase` for git-scoped runs.           |
| `runners`  | Run non-`.md` guides — file extension → command.              |
| `sensors`  | Per-sensor overrides, keyed by sensor name.                   |
| `smells`   | Per-smell routing overrides, keyed by smell key.             |

## `[sensors.<name>]`

| Field      | Meaning                                              |
|------------|-----------------------------------------------------|
| `disabled` | Drop the sensor entirely.                            |
| `args`     | Extra arguments appended to the sensor's `command`.  |
| `files`    | Override the sensor's file globs.                    |

The sensor's `command`, `produces`, and adapter mapping live in its
`sensors/<name>.toml` spec, not here (see [sensors.md](sensors.md)). This block
only tunes a sensor the plugin already defines, or disables one.

## `[smells.<name>]`

| Field      | Meaning                                                            |
|------------|-------------------------------------------------------------------|
| `severity` | `enforced` (fails the run) or `suggested` (coaches, exit 0).      |
| `disabled` | Drop this smell — it is neither coached nor counted.             |
| `guide`    | Use a named guide file instead of `<smell>.md`.                  |
| `include` / `exclude` | Glob filters scoping where the smell applies.         |

A smell with no override uses the catalogue default
([smell-vocabulary.md](smell-vocabulary.md)).

## `[runners]`

Maps a guide file extension to the command that runs it: the mapper runs
`<command> guides/<smell>.<ext>` with the finding on stdin. `.md` is always
rendered as a template and needs no runner; every other extension needs one, so
no guide executes unless you opt in.

```toml
[runners]
py = "python"
js = "node"
```

## Custom smells

A project (or plugin) sensor may emit a smell not in the catalogue. Declare it
under `smells` with a `title` and `severity` so it routes the way you want
rather than escalating with the generic uncoached prompt:

```toml
[smells.custom-marker]
severity = "enforced"
title = "Custom marker"
description = "flagged by the project's own sensor"
```

Pair it with a sensor spec that `produces` it and a `guides/custom-marker.md`.
