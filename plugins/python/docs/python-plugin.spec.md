# The python plugin — acceptance

The python plugin runs its sensors through the real `habit-sensors` pipeline.
These cases run the **actual** tools (`ruff`, `deptry`) against a fixture with a
known smell and assert the canonical finding comes out, mapped to the smell keys
in [smell-vocabulary.md](smell-vocabulary.md).

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
```

## ruff adapter maps rule IDs to canonical smells

The `ruff` adapter selects `C901,PLR0913,PLR0915,F841,F401,BLE001` and a jq
transform in its command groups the flat output into one finding per smell,
stamping `source: "ruff:<code>"` on each issue. The shipped `ruff.toml` carries
`max-args = 3`, so a four-argument function trips `PLR0913`.

📄ruff.toml @plugins/python/src/habit_hooks_python/ruff.toml

📄pyproject.toml
```toml
[project]
name = "demo"
version = "0.0.0"
```

📄billing.py
```python
import os


def charge(a, b, c, d):
    unused = 1
    return a + b + c + d
```

```bash
habit-sensors --all | jq 'sort_by(.smell)[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "language": "python",
  "key": "billing.py",
  "line": 4,
  "source": "ruff:PLR0913"
}
{
  "smell": "unused-import",
  "language": "python",
  "key": "billing.py",
  "line": 1,
  "source": "ruff:F401"
}
{
  "smell": "unused-variable",
  "language": "python",
  "key": "billing.py",
  "line": 5,
  "source": "ruff:F841"
}
```

## An empty scope runs no sensor, so ruff never scans the whole tree

A scoped run that resolves to **zero** files measured nothing, and no sensor may
run over it. `ruff` handed no paths falls back to its own default — scan the
current directory — so without this guard a non-source-only change reports every
legacy smell in the tree and fails the run (#93). Here `[files]` counts only
`**/*.py` as source (the plugin default) and `--file README.md` names a doc, so
the scope is empty even though `legacy.py` carries three real smells. The run
emits `[]` and exits 0, and the scope layer still says on stderr that it scanned
nothing.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.deptry]
disabled = true
```

📄ruff.toml @plugins/python/src/habit_hooks_python/ruff.toml

📄pyproject.toml
```toml
[project]
name = "demo"
version = "0.0.0"
```

📄legacy.py
```python
import os


def charge(a, b, c, d):
    unused = 1
    return a + b + c + d
```

📄README.md
```text
# docs
```

```bash
habit-sensors --file README.md
```

🖥️ ✅
```json
[]
```

🚨
```text
habit-sensors: --file 'README.md' is outside [files]; nothing scanned
```

## ruff maps a syntax error to parse-error

A file ruff cannot parse surfaces as `parse-error` (ruff reports it as
`invalid-syntax`), not a null smell, so a broken file is still coached rather
than silently mislabelled. This mirrors the TS plugin, where `eslint:fatal`
maps to `parse-error`.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.deptry]
disabled = true
```

📄ruff.toml @plugins/python/src/habit_hooks_python/ruff.toml

📄broken.py
```python
def broken(:
    return 1
```

```bash
habit-sensors --all | jq '.[] | {smell, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "parse-error",
  "source": "ruff:invalid-syntax"
}
```

## deptry sensor maps DEP002 to unused-dependency

The `deptry` sensor runs deptry against a temp JSON report and shapes each
`DEP002` (a declared but unused dependency) into an `unused-dependency` finding,
one issue per module keyed by the module name.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.ruff]
disabled = true
```

📄pyproject.toml
```toml
[project]
name = "demo"
version = "0.0.0"
dependencies = ["requests", "rich"]
```

📄app.py
```python
import requests


def fetch(url):
    return requests.get(url).text
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "unused-dependency",
  "language": "python",
  "key": "rich",
  "file": "pyproject.toml",
  "source": "deptry:DEP002"
}
```

## A crashing deptry fails the run, never reports clean

deptry needs a `pyproject.toml` to analyse; without one it exits non-zero
instead of emitting findings. The sensor must surface that as a failure — a
crashed tool is never a clean run. The sensor exits with a code outside the
findings range, so `habit-sensors` raises, names the sensor on stderr, and exits
1 rather than printing an empty (false-clean) result. The failed run carries only
the reserved `incomplete-run` marker on stdout
([habit-sensors.spec.md](../../../docs/habit-sensors.spec.md)).

The notice carries deptry's own diagnosis after that first line. That text is
deptry's to word and names absolute paths, so only the line naming the sensor is
asserted here.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.ruff]
disabled = true
```

📄app.py
```python
def fetch(url):
    return url
```

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
```

```bash
habit-sensors --all 2>&1 >/dev/null | sed -n 1p
```

🖥️ ❌ 1
```text
habit-sensors: sensor 'deptry' failed: ${python} ${dir}/deptry_sensor.py
```

## A crashing ruff fails the run, never reports clean

The `ruff` sensor pipes the tool into `jq`. A crashing `ruff` (here, a malformed
`ruff.toml` that makes the tool exit non-zero) prints nothing on stdout, so a
naive pipe would let `jq` succeed on empty input and mask the crash as a false-
clean run. The command sets `pipefail` so the tool's failing exit propagates
through the pipe; `habit-sensors` then raises, names the sensor on stderr, and
exits 1, carrying only the reserved `incomplete-run` marker on stdout
([habit-sensors.spec.md](../../../docs/habit-sensors.spec.md)).

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.deptry]
disabled = true
```

📄ruff.toml
```toml
this is not = valid ruff config
```

📄app.py
```python
import os
```

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
```

The notice quotes the sensor's whole command — multi-line here, so its first
line shows only where that command starts — and then ruff's own diagnosis, which
names the absolute path of the config it could not parse. Only the line naming
the sensor is stable enough to assert.

```bash
habit-sensors --all 2>&1 >/dev/null | sed -n 1p
```

🖥️ ❌ 1
```text
habit-sensors: sensor 'ruff' failed: set -o pipefail
```
