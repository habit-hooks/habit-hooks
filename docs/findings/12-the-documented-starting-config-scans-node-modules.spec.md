# 12. The documented starting config scans `node_modules`

Two pieces of documentation debt, both found by the same cold-start user setting
habit-hooks up on a TypeScript project for the first time. Neither is a bug in
the code; both make the code do something the reader did not ask for.

**(a) The worked example scans other people's code.**
[config.md](../config.md) shows `files = ["**/*.ts", "**/*.tsx"]`. Copy that and
the run walks `node_modules`, because `files` is a pathspec allow-list, not a
`.gitignore` reader — only gitignore *syntax* is borrowed, and no ignore file is
consulted. In the study, **45 of 46 findings** came from
`node_modules/typescript/lib/*.d.ts` and friends. The fix is one negation:

```toml
files = ["**/*.ts", "**/*.tsx", "!node_modules/**"]
```

and it appears in no example anywhere. The doc mentions the mechanism once, in a
subordinate clause — "a later pattern can negate an earlier one" — under
"`files` defaults to what the plugins declare", where a reader configuring their
first project has no reason to be. Note that #97 (discovery is opt-in) does not
help here: it protects a project that names *no* source, and this project names
some.

**(b) A documented per-sensor override that does nothing.**
[config.md](../config.md)'s `[sensors.<name>]` table offers
`args` — "replace the sensor's default CLI args, expanded into its command via
`${args}`". The second half is the catch, and it is not a warning: a sensor whose
command contains no `${args}` cannot receive them, so the setting is accepted,
merged, and dropped on the floor. **All three sensors the typescript plugin ships
are in exactly that state**:

```text
$ grep -h '^command' plugins/typescript/src/habit_hooks_typescript/sensors/*.toml
command = "node ${dir}/comment.js ${files}"
command = """
command = "node ${dir}/knip.js"
```

`comment` and `knip` say it in one line; `eslint`'s is the multi-line shell script
whose opening `"""` is the third line above, and it has no `${args}` either (the
third Today case reads all three out of the installed package). So a TypeScript
project reading the table and writing `[sensors.eslint] args = […]` gets silence:
no error, no warning, no effect. Across all four shipped plugins exactly **one**
sensor expands `${args}` at all — `generic`'s `line-count` — so the override is
inert for seven of the eight sensors that ship.

**Prose-only, but the same class:** the install list in
[README.md](../../README.md) says the typescript plugin needs "`eslint`, `knip`,
and `jq`". Getting the plugin working also needed `ts-morph` (the `comment`
sensor `require`s it), `@typescript-eslint/parser` **and**
`@typescript-eslint/eslint-plugin` (the shipped `eslint.config.mjs` imports both
at the top), and an eslint new enough for flat config — the plugin's own
`package.json` pins `eslint ^10.4.0`. None of those four facts is written down
anywhere a consumer looks. There is nothing to assert here; it is a list that
needs four entries added.

## Today

### The documented TypeScript globs sweep `node_modules`

Delete this case when the docs are fixed.

`files` is copied verbatim from [config.md](../config.md)'s worked example. The
sensor reports back exactly the files it was handed: one is the project's, three
belong to packages it installed. A `.gitignore` naming `node_modules/` sits right
there and changes nothing — only the gitignore *syntax* is borrowed, never the
file.

📄.habit-hooks/config.toml
```toml
plugins = ["generic", "typescript"]
files   = ["**/*.ts", "**/*.tsx"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["echo-files"]
```

📄.habit-hooks/typescript/config.toml
```toml
language = "typescript"
sensors  = []
```

📄.habit-hooks/generic/sensors/echo-files.toml
```toml
command = "jq -n --args '[{smell: \"oversized-file\", details: {}, issues: ($ARGS.positional | map({key: ., details: {file: .}}))}]' ${files}"
```

📄.gitignore
```text
node_modules/
```

📄src/app.ts
```typescript
export const answer = 42;
```

📄node_modules/typescript/lib/lib.dom.d.ts
```typescript
declare const document: unknown;
```

📄node_modules/typescript/lib/typescript.d.ts
```typescript
declare const ts: unknown;
```

📄node_modules/knip/dist/index.d.ts
```typescript
declare const knip: unknown;
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["node_modules/knip/dist/index.d.ts","node_modules/typescript/lib/lib.dom.d.ts","node_modules/typescript/lib/typescript.d.ts","src/app.ts"]
```

### The one-line fix works — keep this case

**Keep this case after the docs are fixed.** It pins the negation the example
should carry, so the mechanism cannot quietly stop working underneath the text
that finally documents it.

📄.habit-hooks/config.toml
```toml
plugins = ["generic", "typescript"]
files   = ["**/*.ts", "**/*.tsx", "!node_modules/**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["echo-files"]
```

📄.habit-hooks/typescript/config.toml
```toml
language = "typescript"
sensors  = []
```

📄.habit-hooks/generic/sensors/echo-files.toml
```toml
command = "jq -n --args '[{smell: \"oversized-file\", details: {}, issues: ($ARGS.positional | map({key: ., details: {file: .}}))}]' ${files}"
```

📄src/app.ts
```typescript
export const answer = 42;
```

📄node_modules/typescript/lib/typescript.d.ts
```typescript
declare const ts: unknown;
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/app.ts"]
```

### No shipped TypeScript sensor can consume `args`

Delete this case when the fix lands.

Read straight out of the installed package data, so it stays true whatever the
override chain does in a consumer. All three answer the same way.

```bash
python - <<'PY'
from importlib.resources import files

sensors = files("habit_hooks_typescript") / "sensors"
for name in ["eslint", "knip", "comment"]:
    print(f"{name}: consumes args = {'${args}' in (sensors / f'{name}.toml').read_text()}")
PY
```

🖥️ ✅
```text
eslint: consumes args = False
knip: consumes args = False
comment: consumes args = False
```

### Setting `args` on such a sensor is accepted and ignored

Delete this case when the fix lands.

`quiet` stands in for `eslint`/`knip`/`comment`: a sensor with default `args` in
its own spec and no `${args}` in its command. The project replaces those args —
the documented override — and the run reports the same thing it would have
without the setting. Exit 0, nothing on stderr, no hint that a configured value
was discarded.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]

[sensors.quiet]
args = ["--max", "500"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["quiet"]
```

📄.habit-hooks/generic/sensors/quiet.toml
```toml
command = "jq -nc --args '[{smell: \"oversized-file\", details: {argv: $ARGS.positional}, issues: []}]' --"
args    = ["--max", "200"]
```

📄src/app.txt
```text
app
```

```bash
habit-sensors --all | jq -c '.[0].details'
```

🖥️ ✅
```json
{"argv":[]}
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
```

### `args` reaches a sensor whose command expands it — keep this case

**Keep this case after the fix.** The discriminator, and the behaviour any
refusal must not break: the same override, on a sensor that spells `${args}`,
replaces the spec's defaults wholesale and arrives on the command line.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]

[sensors.loud]
args = ["--max", "500"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["loud"]
```

📄.habit-hooks/generic/sensors/loud.toml
```toml
command = "jq -nc --args '[{smell: \"oversized-file\", details: {argv: $ARGS.positional}, issues: []}]' -- ${args}"
args    = ["--max", "200"]
```

📄src/app.txt
```text
app
```

```bash
habit-sensors --all | jq -c '.[0].details'
```

🖥️ ✅
```json
{"argv":["--max","500"]}
```

## Wanted

The first two are edits to [config.md](../config.md); the third is a guard so
this class of "documented, accepted, inert" cannot recur. The doc cases below
copy the real file into the case directory and assert against it, so they go
green the moment the example is fixed and stay green afterwards.

### The worked TypeScript example excludes `node_modules` 🟡

The example a first-time reader copies must not scan somebody else's code.

📄config.md @docs/config.md

```bash
grep -q '!node_modules/\*\*' config.md && echo excluded
```

🖥️ ✅
```text
excluded
```

### The Python examples exclude the virtualenv directory 🟡

`files = ["**/*.py"]` has the same shape and the same hazard, one vendor
directory along.

📄config.md @docs/config.md

```bash
grep -q '!\.venv/\*\*' config.md && echo excluded
```

🖥️ ✅
```text
excluded
```

### `args` on a sensor that cannot expand them is refused by name 🟡

The same fixture as the Today case. A setting nothing consumes is a typo or a
dead key — the argument #102 already makes for config keys — so it fails at load
time, before any sensor runs, naming the sensor and why.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]

[sensors.quiet]
args = ["--max", "500"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["quiet"]
```

📄.habit-hooks/generic/sensors/quiet.toml
```toml
command = "jq -nc --args '[{smell: \"oversized-file\", details: {argv: $ARGS.positional}, issues: []}]' --"
args    = ["--max", "200"]
```

📄src/app.txt
```text
app
```

```bash
habit-sensors --all
```

🖥️ ❌ 2

🚨
```text
habit-sensors: [sensors.quiet] sets 'args', but the sensor's command has no ${args} to expand them into — replace the whole sensors/quiet.toml instead
```
