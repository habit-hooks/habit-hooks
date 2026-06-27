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

Here is a native sensor that flags `TODO` comments — `grep` piped through `jq`,
no linter required:

```toml
# plugins/lua/sensors/todo.toml
command  = "grep -rn TODO ${files} | jq -Rn '<jq below>'"
produces = ["warning-comment"]
language = "lua"
```

`habit-sensors` expands `${files}` and runs the command. Run it directly against
a sample file to see the findings it emits:

📄src/util.lua
```lua
local function add(a, b)
  -- TODO: validate inputs
  return a + b
end
```

```bash
grep -rn TODO src | jq -Rn '[inputs
  | capture("(?<file>[^:]+):(?<line>[0-9]+):(?<text>.*)")
  | {smell: "warning-comment", language: "lua",
     details: {file: .file, line: (.line|tonumber),
               message: (.text | gsub("^\\s*--\\s*"; ""))}}]'
```

🖥️ ✅
```text
[
  {
    "smell": "warning-comment",
    "language": "lua",
    "details": {
      "file": "src/util.lua",
      "line": 2,
      "message": "TODO: validate inputs"
    }
  }
]
```

To wrap a linter that already emits JSON instead, map its output with `jq` the
same way — see [adapter-jq-based.spec.md](adapter-jq-based.spec.md).

## 2. Coach the fix — a guide

For each smell, author a `guides/<smell>` fix ([guide.md](guide.md)). A
**template** `guides/<smell>.md` is Nunjucks, rendered against the finding's
`details` bag (`smell`/`language` also in scope):

```markdown
<!-- plugins/lua/guides/warning-comment.md -->
{% for i in issues %}{{ i.file }}:{{ i.line }} — {{ i.message }}
{% endfor %}
Resolve or remove these markers before merging.
```

Or make it a script in any language — `guides/<smell>.py`, say — run by the
**fix runner** you register for that extension (`[runners]` in `config.toml`);
it receives the finding on stdin and its exit code drives pass/fail. Author a
guide only where the language
needs its own wording; otherwise the smell falls back to the generic guide, or
the `uncoached.md` default.

## 3. Wire it up — config.toml

`plugins/<language>/config.toml` sets the language's defaults
([config.md](config.md)):

```toml
# plugins/lua/config.toml
files = ["**/*.lua"]            # what this language's sensors scan

[smells.warning-comment]
severity = "suggested"         # enforced (exit 1) | suggested (exit 0)
```

Anything omitted falls back to the catalogue and generic defaults.

## 4. Try it

```bash
habit-sensors --all | habit-mapper
```

A Lua file with a `TODO` now surfaces `warning-comment`, routed to your guide.
What each piece guarantees is pinned in [sensors.md](sensors.md),
[adapter-jq-based.spec.md](adapter-jq-based.spec.md), and
[mapper.spec.md](mapper.spec.md).
