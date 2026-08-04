# 04. Repeated `--file` flags silently keep the last

`habit-sensors --file a.js --file b.js --file c.js` looks like it scans three
files. It scans one — `c.js` — because `--file` is a plain
`add_argument("--file")` (`src/habit_hooks/sensors/__init__.py`), and argparse's
default `store` action overwrites on every repeat. No error, no warning, no hint
in the output that two of the three paths were dropped on the floor.

The damage is not the missed scan, it is the confident answer:

```text
$ habit-hooks --file src/a.js --file src/b.js --file src/c.js
✅ Habit Hooks: automated checks passed.
$ echo $?
0

$ habit-hooks --all
── loose-equality (2 issues) ──
src/a.js:1
src/b.js:1
```

`src/c.js` is genuinely clean, so the run that saw only `src/c.js` genuinely
passes — and reports a pass over `src/a.js` and `src/b.js`, which it never
opened. In the field study a coached agent, having edited three files, asked
after all three in one command and was told its change set was clean. It believed
that. So would anyone.

Repeating a flag is not an exotic mistake: it is exactly what a caller does when
it has a list, and every other `--file`-taking tool in a developer's day
(`ruff`, `eslint`, `jq`) accepts several paths. Note also that `--file` sets
`_bypasses_snooze`, so the mode is already the "tell me everything about the
files I name" mode — which makes silently dropping most of them worse.

Every case below shares a sensor that flags loose equality in the files it is
handed, so what was scanned is visible in the output. `src/a.js` and `src/b.js`
smell; `src/c.js` does not. Discovery is opt-in (#97), so the config names a
scope.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "grep -lE '[^=]==[^=]' ${files} | jq -R . | jq -s 'if length == 0 then [] else [{smell: \"loose-equality\", details: {maxAllowed: 0}, issues: map({key: ., details: {file: ., line: 1}})}] end'"
```

📄.habit-hooks/generic/guides/loose-equality.md
```markdown
Use === instead of ==:

{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }}
{% endfor %}
```

📄.habit-hooks/generic/guides/clean.md
```markdown
✅ Habit Hooks: automated checks passed.
```

📄src/a.js
```js
export const equal = (a, b) => a == b;
```

📄src/b.js
```js
export const same = (a, b) => a == b;
```

📄src/c.js
```js
export const strict = (a, b) => a === b;
```

## Today

### Three `--file` flags produce a clean report over two smelly files

Delete this case when the fix lands.

Asked about all three files, the run scans only the last one and reports a pass —
while `--all` over the very same three files finds two smells.

```bash
habit-hooks --file src/a.js --file src/b.js --file src/c.js
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.
```

The two files it claimed were fine:

```bash
habit-hooks --all
```

🖥️ ❌ 1
```text
── loose-equality (2 issues) ──

Use === instead of ==:

src/a.js:1
src/b.js:1
```

Each of them, asked after on its own, reports the smell — so the clean answer
above was about scanning, not about the code:

```bash
habit-hooks --file src/a.js
```

🖥️ ❌ 1
```text
── loose-equality (1 issue) ──

Use === instead of ==:

src/a.js:1
```

### The last flag wins, whichever one it is

Delete this case when the fix lands.

Not "the first wins" and not "they merge": the surviving path is whichever
`--file` was written last, so reordering the same command changes the answer.

```bash
habit-sensors --file src/a.js --file src/b.js --file src/c.js | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

```bash
habit-sensors --file src/c.js --file src/b.js --file src/a.js | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/a.js"]
```

### Nothing is said about the dropped paths

Delete this case when the fix lands.

Not on stdout, and not on stderr either — the two discarded paths leave no trace
anywhere in the run.

```bash
habit-sensors --file src/a.js --file src/b.js --file src/c.js 2>&1 >/dev/null | wc -l | tr -d ' '
```

🖥️ ✅
```text
0
```

## Wanted

A silent wrong answer is the thing to eliminate. Either of these two fixes does
that; only one of them should be built.

**Accept several paths** (`action="append"`, or `nargs="+"`) is the friendlier
one and matches what every other tool does. `scope._selected` already returns a
list — `[args.file]` becomes `args.file` — and `_source_files` narrows the whole
list exactly as it narrows one path today, so `--file` on a path outside
`[files]` keeps its per-file notice.

**Reject a repeated flag** (an argparse usage error, exit 2) is the smaller
change and still removes the trap: the caller finds out immediately instead of
being told its unscanned files are fine.

### Every named file is scanned 🟡

The append fix: all three paths are measured, and the two smelly ones are
reported.

```bash
habit-hooks --file src/a.js --file src/b.js --file src/c.js
```

🖥️ ❌ 1
```text
── loose-equality (2 issues) ──

Use === instead of ==:

src/a.js:1
src/b.js:1
```

### One `--file` still behaves exactly as it does today 🟡

Whichever fix lands, the single-path spelling that every hook in the wild uses
must not change.

```bash
habit-hooks --file src/a.js
```

🖥️ ❌ 1
```text
── loose-equality (1 issue) ──

Use === instead of ==:

src/a.js:1
```

### Or a repeated flag is a usage error 🟡

The alternative fix. Exit 2 is the code the CLI reserves for a failure of the
tool itself rather than a finding (`cli.py`), which is what a malformed
invocation is.

```bash
habit-sensors --file src/a.js --file src/b.js
```

🖥️ ❌ 2

🚨
```text
habit-sensors: --file given more than once; it takes a single path
```
