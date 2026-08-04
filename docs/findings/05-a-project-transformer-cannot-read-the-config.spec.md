# 05. A project transformer cannot read the config

`habit_hooks.config.load_config()` grew a **required** keyword-only `program`
argument, so that each binary names itself when it rejects a config key. Every
caller outside this repository was updated by nobody, and there are callers: a
transformer is its own process, and the only way one has ever been able to read
`[scope] branchBase` is to import this function.

```text
$ python -c 'from pathlib import Path
> from habit_hooks.config import load_config
> print(load_config(Path.cwd()).scope.branchBase)'
TypeError: load_config() missing 1 required keyword-only argument: 'program'
```

That is the shallow half. The expensive half is what a real transformer does with
the exception. The 3dmaze project ships a `snooze-until-changed`-style ratchet
that reads `branchBase` exactly this way, wraps the whole thing in a broad
`except`, and — deliberately — **fails towards noise**: on any error it passes
every finding through and exits 0, on the theory that reporting too much is safer
than reporting too little. After the argument landed, that project's runs
re-published all 208 previously-snoozed findings, 225 KB of coaching, with **0
bytes on stderr** and exit 0. Nothing in the output said the ratchet had stopped
working. It read as a repository that had suddenly acquired 208 new smells.

Both halves are one product gap, and the second is the one that hides the first.
A sensor that fails is quoted, counted, and turned into an `incomplete-run`
finding (#88) — but the conditions that trigger any of it are all about the exit
code and **stdout**: a non-zero exit, empty stdout, or output that will not parse
(`part_output.sensor_crashed`, `execution._transform`). A part that exits 0 and
prints a valid findings array is believed unconditionally, and `part_failure` —
reached only from those conditions — is the only thing that ever quotes a part's
stderr back to the user. So a part that fails *successfully* has its own
explanation discarded unread.

**Is `habit_hooks.config` public API?** Nothing in `docs/` says so. The only
documented Python-level surfaces are the `habit_hooks.plugins` entry-point group
([architecture.md](../architecture.md),
[authoring-plugins.spec.md](../authoring-plugins.spec.md)) and
`${python} -m habit_hooks.snooze`, used as a *command* by the shipped
`snooze-until-changed` spec. So importing `load_config` is reaching into an
internal — but there is no supported alternative. What *is* documented for
transformers ([authoring-plugins.spec.md](../authoring-plugins.spec.md), "4.
Write a transformer") is `${config}`, and that placeholder expands to
`--config <path>` **only when the run named one**, to nothing otherwise. On a
default run a transformer is handed no path at all, leaving it to hard-code
`.habit-hooks/config.toml` and re-implement the plugin merge by hand, or to
import the internal. Every case below is written against a transformer that took
the second road, because that is what the field does.

Every case runs the real pipeline. Discovery is opt-in (#97), so the config names
a scope; the fixture files are `.txt` so the run makes no plugin recommendation
and stderr carries only what this finding is about.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
files        = ["src/**"]
transformers = ["ratchet"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "cat ${dir}/alpha.json"
```

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"oversized-file","details":{},"issues":[
  {"key":"src/big.txt","details":{"file":"src/big.txt"}},
  {"key":"src/ok.txt","details":{"file":"src/ok.txt"}}]}]
```

📄.habit-hooks/generic/transformers/ratchet.toml
```toml
command = "${python} ${dir}/ratchet.py"
```

📄.habit-hooks/snooze.json
```json
["src/big.txt", "src/ok.txt"]
```

📄src/big.txt
```text
big
```

📄src/ok.txt
```text
ok
```

## Today

### A third-party caller of `load_config` dies on the new argument

Delete this case when the fix lands.

The call is the documented-nowhere-but-only-possible one: hand it the project
directory and read `[scope] branchBase` off the result. It worked in 1.0.x. It
raises `TypeError` now, and no deprecation period sat between the two.

```bash
python -c 'from pathlib import Path
from habit_hooks.config import load_config
print(load_config(Path.cwd()).scope.branchBase)' 2>&1 | tail -1
```

🖥️ ❌ 1
```text
TypeError: load_config() missing 1 required keyword-only argument: 'program'
```

### A transformer that reads the config that way fails the whole run

Delete this case when the fix lands.

Put the same call inside a transformer and the run fails loudly — which is the
*good* outcome, and the one this project's own machinery is built for: a notice
naming the part, its own words quoted back, exit 1, and an `incomplete-run`
finding on the pipe. Only the first and last stderr lines are asserted; the
traceback between them carries the case's temporary path.

📄.habit-hooks/generic/transformers/ratchet.py
```python
import json
import sys
from pathlib import Path

from habit_hooks.config import load_config

base = load_config(Path.cwd()).scope.branchBase
snoozed = set(json.loads(Path(".habit-hooks/snooze.json").read_text()))
findings = json.load(sys.stdin)
for finding in findings:
    finding["issues"] = [i for i in finding["issues"] if i["key"] not in snoozed]
json.dump(findings, sys.stdout)
```

```bash
habit-sensors --all 2>&1 >/dev/null | sed -n '1p;$p'
```

🖥️ ❌ 1
```text
habit-sensors: transformer 'ratchet' failed: ${python} ${dir}/ratchet.py
TypeError: load_config() missing 1 required keyword-only argument: 'program'
```

### A transformer that catches the error and exits 0 is invisible

Delete this case when the fix lands.

This is the 3dmaze transformer, shrunk to two keys. It catches broadly, writes a
diagnosis to stderr, passes everything through, and exits 0 — "fail towards
noise". The run believes it: both snoozed keys come back, there is no
`incomplete-run` finding, the exit code is 0, and the transformer's own
explanation of why it gave up never reaches the user.

📄.habit-hooks/generic/transformers/ratchet.py
```python
import json
import sys
from pathlib import Path

findings = json.load(sys.stdin)
try:
    from habit_hooks.config import load_config

    base = load_config(Path.cwd()).scope.branchBase
    snoozed = set(json.loads(Path(".habit-hooks/snooze.json").read_text()))
    for finding in findings:
        finding["issues"] = [i for i in finding["issues"] if i["key"] not in snoozed]
except Exception as error:
    print(f"ratchet: cannot read the config ({error}); reporting everything", file=sys.stderr)
json.dump(findings, sys.stdout)
```

Every snoozed key is back on the pipe:

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/big.txt","src/ok.txt"]
```

Nothing marks the run as incomplete:

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ✅
```json
["oversized-file"]
```

And stderr — where the transformer wrote its diagnosis — is empty:

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
```

### A transformer that exits non-zero still gets its stderr quoted — keep this case

**Keep this case after the fix.** It pins the channel that already works, so a
change that surfaces stderr from a *successful* part must not disturb what a
failing one already says.

📄.habit-hooks/generic/transformers/ratchet.py
```python
import sys

print("ratchet: cannot read the config; refusing to guess", file=sys.stderr)
sys.exit(1)
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ❌ 1
```text
habit-sensors: transformer 'ratchet' failed: ${python} ${dir}/ratchet.py
ratchet: cannot read the config; refusing to guess
```

## Wanted

Three separable fixes; the first two are independent of each other.

1. **`program` defaults.** `load_config(project_dir, config_path=None, *,
   program: str = "habit-hooks")` keeps every existing caller working while the
   three console scripts go on naming themselves. The argument exists so a
   rejected key names the binary the user ran; a default named after the product
   is wrong for nobody and fatal for nobody.
2. **A part's stderr is surfaced whether or not it exited 0.** `part_failure` is
   the only thing that quotes a part's own words today, and it is reached only
   from a non-zero exit. A part that printed to stderr *said something*, and the
   run's only "somebody has to look at this" channel is stderr — the same
   argument #79 made for aliasing notices.
3. **A documented way for a transformer to read the config it is running under.**
   `${config}` should expand to the config the run actually loaded, including the
   default `.habit-hooks/config.toml`, so a transformer never has to import an
   internal or guess a path.

### `load_config` still answers a caller that does not name a program 🟡

The 1.0.x call, unchanged, still works.

```bash
python -c 'from pathlib import Path
from habit_hooks.config import load_config
print(load_config(Path.cwd()).scope.branchBase)'
```

🖥️ ✅
```text
main
```

### A transformer's diagnosis reaches stderr even when it exits 0 🟡

Same "fail towards noise" transformer as the Today case. It still exits 0 and its
findings still pass through — but what it wrote to stderr is no longer thrown
away, so the user can see that the ratchet stopped ratcheting.

📄.habit-hooks/generic/transformers/ratchet.py
```python
import json
import sys

findings = json.load(sys.stdin)
print("ratchet: cannot read the config; reporting everything", file=sys.stderr)
json.dump(findings, sys.stdout)
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
habit-sensors: transformer 'ratchet' wrote to stderr: ratchet: cannot read the config; reporting everything
```

### `${config}` hands a transformer the config the run loaded 🟡

No `--config` flag is given, so the run loads the default
`.habit-hooks/config.toml` — and the transformer is told which file that was,
instead of being handed an empty string and left to hard-code the path.

📄.habit-hooks/generic/transformers/ratchet.toml
```toml
command = "${python} ${dir}/ratchet.py ${config}"
```

📄.habit-hooks/generic/transformers/ratchet.py
```python
import json
import sys

print(f"ratchet got: {' '.join(sys.argv[1:])}", file=sys.stderr)
json.dump(json.load(sys.stdin), sys.stdout)
```

```bash
habit-sensors --all 2>&1 >/dev/null | sed 's#/.*/\.habit-hooks#.habit-hooks#'
```

🖥️ ✅
```text
ratchet got: --config .habit-hooks/config.toml
```
