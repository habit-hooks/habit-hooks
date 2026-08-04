# 10. Broken input answers with a Python traceback

Three separate first-contact mistakes — asking for help, mistyping a config,
running a tool you have not installed — all get the same answer: a raw Python
stack trace ending in a library exception. Every one of them is a thing a person
does in their first ten minutes with habit-hooks, and the tool's own error
handling is good everywhere else, which is what makes these stand out.

```text
$ habit-hooks --help
Traceback (most recent call last):
  ...
  File ".../habit_hooks/mapper.py", line 62, in read_findings
    return json.loads(raw) if raw else None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
$ echo $?
1
```

That one is a plumbing accident: `habit-hooks` is
`habit-sensors $ARGS | habit-mapper`, `--help` is forwarded to `habit-sensors`,
argparse prints the usage text onto **stdout** — which is the pipe — and
`habit-mapper` tries to parse the word `usage:` as JSON. `--version` is already
special-cased in `hooks.py` for precisely this reason (*"forwarded to
habit-sensors it would print the version onto the pipe where habit-mapper expects
findings JSON"*); `--help` and `-h` were not. The usage text is never seen by
anybody: it is eaten by the pipe.

The other two are missing guards on the way in. A malformed
`.habit-hooks/config.toml` reaches `tomllib.load` unprotected
(`config._read_toml`) and additionally **exits 1** — the code `cli.py` reserves
for *an enforced finding*, not for *the tool failed*, so CI reading the exit code
concludes the code has a smell. And a configured sensor whose tool is absent
answers with `FileNotFoundError: [Errno 2] No such file or directory: 'jscpd'`
instead of "jscpd is not installed".

Contrast all three with the config loader's *unknown key* message, which is
exactly right and is pinned below as a keeper:

```text
$ habit-sensors --all
habit-sensors: unknown config key 'fyles' in the project config; known keys: files, plugins, runners, scope, sensors, smells, transformers
$ echo $?
2
```

Same file, one character's difference in the mistake, and two entirely different
qualities of answer.

The fixture below is the smallest working project; individual cases replace parts
of it. Discovery is opt-in (#97), so the config names a scope.

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
command = "echo '[]'"
```

📄.habit-hooks/generic/guides/clean.md
```markdown
✅ Habit Hooks: automated checks passed.
```

📄src/x.js
```js
export const strict = (a, b) => a === b;
```

## Today

### `--help` answers with a JSONDecodeError

Delete this case when the fix lands.

The traceback's middle is absolute paths and line numbers, so only its first and
last lines are asserted. The exit code is 1.

```bash
habit-hooks --help 2>&1 | sed -n '1p;$p'
```

🖥️ ❌ 1
```text
Traceback (most recent call last):
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

`-h` is the same command spelled shorter, and fails the same way:

```bash
habit-hooks -h 2>&1 | sed -n '1p;$p'
```

🖥️ ❌ 1
```text
Traceback (most recent call last):
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

The stage binaries' own `--help` is fine — which is why the breakage is easy to
miss when you build the tool and hard to miss when you first use it. **Keep this
half after the fix**: whatever `habit-hooks --help` grows must not disturb it.

```bash
habit-sensors --help | head -1
```

🖥️ ✅
```text
usage: habit-sensors [-h] [--version] [--config CONFIG] [--no-snooze]
```

### A malformed config answers with a TOMLDecodeError, and exits 1

Delete this case when the fix lands.

The config has an unclosed array — one missing `]`, the commonest hand-edit
mistake there is. Nothing reaches stdout, and the exit code is **1**, which by
`cli.py`'s contract means "an enforced smell was found in your code". It was not:
the tool never ran.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"
```

```bash
habit-sensors --all 2>/dev/null
```

🖥️ ❌ 1
```text
```

The parenthetical position varies with the mistake, so it is scrubbed; the class
and message are the tool's whole answer.

```bash
habit-sensors --all 2>&1 >/dev/null | sed -n '1p;$p' | sed 's/ (at .*//'
```

🖥️ ❌ 1
```text
Traceback (most recent call last):
tomllib.TOMLDecodeError: Unclosed array
```

A duplicated table — the other everyday TOML slip — lands in the same place:

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]

[scope]
branchBase = "main"

[scope]
mainBranch = "main"
```

```bash
habit-sensors --all 2>&1 >/dev/null | sed -n '$p' | sed 's/ (at .*//'
```

🖥️ ❌ 1
```text
tomllib.TOMLDecodeError: Cannot declare ('scope',) twice
```

### An unknown config key is answered properly — keep this case

**Keep this case after the fix.** It is the standard the two malformed-TOML cases
above have to be brought up to: one line, no traceback, names the key, names the
alternatives, and exits 2 because the tool failed rather than the code.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
fyles   = ["src/**"]
```

```bash
habit-sensors --all
```

🖥️ ❌ 2

🚨
```text
habit-sensors: unknown config key 'fyles' in the project config; known keys: files, plugins, runners, scope, sensors, smells, transformers
```

### A missing tool answers with a FileNotFoundError

Delete this case when the fix lands.

The generic plugin's `jscpd` sensor shells out to the `jscpd` binary from a
Python helper (`sensors/jscpd.py`), so an absent tool raises out of
`subprocess.run` and the traceback becomes the sensor's diagnosis. `PATH` is
pinned to the virtualenv plus the system directories, so the case is about a tool
that is not installed rather than about whoever's machine it runs on.

📄.habit-hooks/generic/config.toml
```toml
sensors = ["jscpd"]
```

The run does fail, and it fails in the right way — the reserved `incomplete-run`
finding is appended, so a broken tool can never render clean (#88). **Keep this
half after the fix**: only the wording of the diagnosis is wrong.

```bash
PATH="$VIRTUAL_ENV/bin:/usr/bin:/bin" habit-sensors --all 2>/dev/null | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
```

The diagnosis itself is twenty lines of Python internals whose punchline names
the binary only as a filename that could not be found:

```bash
PATH="$VIRTUAL_ENV/bin:/usr/bin:/bin" habit-sensors --all 2>&1 >/dev/null | sed -n '1p;2p;$p'
```

🖥️ ❌ 1
```text
habit-sensors: sensor 'jscpd' failed: ${python} ${dir}/jscpd.py --config ${dir}/../.jscpd.json
Traceback (most recent call last):
FileNotFoundError: [Errno 2] No such file or directory: 'jscpd'
```

## Wanted

None of the three needs new machinery — `cli.py` already has `ToolError` and its
exit 2, and the config loader already shows what a good message reads like.

- **`--help`** joins `--version` in `hooks.py`: answered before anything is
  spawned, so no usage text is ever written into the pipe.
- **Malformed TOML** is caught in `config._read_toml` and re-raised as the
  `ConfigError` an unknown key already raises — file, line, column, exit 2.
- **A missing tool** is recognised where the sensor is run and reported by name,
  with what installs it, instead of being quoted back as a traceback.

### `--help` prints usage 🟡

The pipeline's own usage, listing the scope flags it forwards, at exit 0.

```bash
habit-hooks --help | head -3
```

🖥️ ✅
```text
usage: habit-hooks [-h] [--version] [--config CONFIG] [--no-snooze]
                   [--all | --file FILE | --branch [base] | --last LAST |
                   --since SINCE]
```

### A malformed config is one line at exit 2 🟡

File, line and column — everything needed to go and fix it — and the exit code
that says the tool failed rather than the code.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"
```

```bash
habit-sensors --all 2>&1 >/dev/null | sed 's|/.*/\.habit-hooks/|.habit-hooks/|'
```

🖥️ ❌ 2
```text
habit-sensors: .habit-hooks/config.toml: invalid TOML at line 2, column 19: Unclosed array
```

### A missing tool is named, not raised 🟡

A notice that says which tool is missing and how to get it. The run still fails
and still appends `incomplete-run`; only the diagnosis changes.

📄.habit-hooks/generic/config.toml
```toml
sensors = ["jscpd"]
```

```bash
PATH="$VIRTUAL_ENV/bin:/usr/bin:/bin" habit-sensors --all 2>&1 >/dev/null
```

🖥️ ❌ 1
```text
habit-sensors: sensor 'jscpd' needs the 'jscpd' command, which is not installed — install it (`npm i -D jscpd`) or disable the sensor with [sensors.jscpd] disabled = true
```
