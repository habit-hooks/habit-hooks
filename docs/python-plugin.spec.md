# The python plugin — acceptance

The python plugin runs its sensors through the real `habit-sensors` pipeline.
These cases run the **actual** tools (`ruff`, `deptry`) against a fixture with a
known smell and assert the canonical finding comes out, mapped to the smell keys
in [smell-vocabulary.md](smell-vocabulary.md).

```bash
habit-sensors() { ../../habit-sensors "$@"; }
```

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
```

## ruff adapter maps rule IDs to canonical smells

The `ruff` adapter selects `C901,PLR0913,PLR0915,F841,F401,BLE001` and a jq
transform in its command groups the flat output into one finding per smell,
stamping `source: "ruff:<code>"` on each issue. The shipped `ruff.toml` carries
`max-args = 3`, so a four-argument function trips `PLR0913`.

📄ruff.toml @plugins/python/ruff.toml

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
habit-sensors --all | jq -c 'sort_by(.smell)[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{"smell":"too-many-parameters","language":"python","key":"billing.py","line":4,"source":"ruff:PLR0913"}
{"smell":"unused-import","language":"python","key":"billing.py","line":1,"source":"ruff:F401"}
{"smell":"unused-variable","language":"python","key":"billing.py","line":5,"source":"ruff:F841"}
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
habit-sensors --all | jq -c '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{"smell":"unused-dependency","language":"python","key":"rich","file":"pyproject.toml","source":"deptry:DEP002"}
```

## A crashing deptry fails the run, never reports clean

deptry needs a `pyproject.toml` to analyse; without one it exits non-zero
instead of emitting findings. The sensor must surface that as a failure — a
crashed tool is never a clean run. The sensor exits with a code outside the
findings range, so `habit-sensors` raises, names the sensor on stderr, and exits
1 rather than printing an empty (false-clean) result.

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
habit-sensors --all
```

🖥️ ❌ 1
```json
[]
```

🚨
```text
habit-sensors: sensor 'deptry' failed: python ${dir}/deptry_sensor.py
```
