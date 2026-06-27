# Building a plugin

A plugin teaches Habit Hooks about a language's smells. It is **just files** — no
core code. Ship it in `plugins/<language>/`, or override per-project in
`.habit-hooks/<language>/` (see [architecture.md](architecture.md)).

```
plugins/<language>/
  config.toml      # defaults: file globs, which smells block
  sensors/*.toml   # how to find smells
  guides/          # how to coach each fix
```

## 1. Find the smell — a sensor

A sensor is one `sensors/<name>.toml`. Its `command` runs and prints a JSON array
of `{smell, language, details}` findings ([sensors.md](sensors.md)).

The common case is an **adapter sensor**: wrap a linter that already emits JSON
and reshape its output into findings with `jq`.

```toml
# plugins/lua/sensors/luacheck.toml
command  = "<your-linter> --json ${files} | jq '<transform>'"
produces = ["unused-variable"]
language = "lua"
```

- `produces` — the smell keys it can emit; the runner uses them to schedule and
  activate the sensor.
- `language` — stamped on every finding so the mapper can pick a Lua-specific fix.
- `${files}` — expands to the in-scope file list.

For a complete, verified `jq` transform see
[adapter-jq-based.spec.md](adapter-jq-based.spec.md). With no linter to wrap, a
**native sensor** is any command that prints the findings array itself.

## 2. Coach the fix — a guide

For each smell the sensor produces, author a `guides/<smell>` fix
([guide.md](guide.md)):

- **Template** `guides/<smell>.md` — Nunjucks, rendered against the finding's
  `details` bag (`smell`/`language` also in scope):

  ```markdown
  <!-- plugins/lua/guides/unused-variable.md -->
  {% for i in issues %}{{ i.file }}:{{ i.line }} — {{ i.name }} is never used
  {% endfor %}
  Remove it, or prefix with `_` if it is intentional.
  ```

- **Script** `guides/<smell>` (no `.md`) — receives the finding on stdin; its exit
  code drives pass/fail.

Author a guide only where the language needs its own wording; otherwise the smell
falls back to the generic guide, or the `uncoached.md` default.

## 3. Wire it up — config.toml

`plugins/<language>/config.toml` sets the language's defaults
([config.md](config.md)):

```toml
files = ["**/*.lua"]            # what this language's sensors scan

[smells.unused-variable]
severity = "enforced"          # enforced (exit 1) | suggested (exit 0)
```

Anything omitted falls back to the catalogue and generic defaults.

## 4. Try it

```bash
habit-sensors --all | habit-mapper
```

A Lua file with an unused variable now surfaces `unused-variable`, routed to your
guide, failing the run. What each piece guarantees is pinned in
[sensors.md](sensors.md), [adapter-jq-based.spec.md](adapter-jq-based.spec.md),
and [mapper.spec.md](mapper.spec.md).
