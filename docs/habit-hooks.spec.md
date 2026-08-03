# habit-hooks

`habit-hooks` is the whole tool: the two stages composed over a Unix pipe,
`habit-sensors $ARGS | habit-mapper`. The arguments scope the sensors stage, the
findings flow through the pipe, and the pipeline fails when **either** stage
fails — the mapper's code when it is non-zero, the sensors' otherwise. This
document specs only that composition — argument forwarding and
exit-code propagation; the stages' own behaviour lives in
[habit-sensors.spec.md](habit-sensors.spec.md) and
[habit-mapper.spec.md](habit-mapper.spec.md), and the big picture in
[architecture.md](architecture.md).

A minimal plugin backs every case below: one sensor that emits a single
`too-many-parameters` finding scoped from `${files}`, and a guide for that smell.
Discovery is opt-in (#97), so the config names what to scan; `["**"]` is every
file this fixture writes.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["params"]
```

📄.habit-hooks/generic/sensors/params.toml
```toml
command = "jq -n --args '[{smell: \"too-many-parameters\", details: {maxAllowed: 3}, issues: ($ARGS.positional | map({key: ., details: {file: ., line: 2, actual: 4, signature: \"bill(...)\"}}))}]' ${files}"
```

📄.habit-hooks/generic/guides/too-many-parameters.md
```markdown
The following function definitions have more than {{ details.maxAllowed }} parameters:

{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }}
    {{ v.details.signature }} has {{ v.details.actual }} parameters
{% endfor %}
Bundle related arguments into an object.
```

📄.habit-hooks/generic/guides/clean.md
```markdown
✅ Habit Hooks: automated checks passed.
```

📄src/billing.py
```text
bill
```

📄src/report.py
```text
report
```

## Scope arguments forward to the sensors stage

`habit-hooks --file <path>` forwards `--file` to `habit-sensors`, so the run is
scoped to that one file and the coached output names only it.

```bash
habit-hooks --file src/billing.py
```

🖥️ ❌ 1
```text
── too-many-parameters (1 issue) ──

The following function definitions have more than 3 parameters:

src/billing.py:2
    bill(...) has 4 parameters

Bundle related arguments into an object.
```

## `--config` forwards to the mapper stage, not just the sensors

`--config <path>` has to reach the mapper too, or the run scopes from one config
and sets its exit code from another. `too-many-parameters` is enforced by the
default `.habit-hooks/config.toml`, so the pipeline would fail; `ci.toml` demotes
it to `suggested`. `habit-hooks --config ci.toml` threads that file into both
stages, so the smell is coached but the pipeline exits 0.

📄ci.toml
```toml
plugins = ["generic"]
files = ["**"]

[smells.too-many-parameters]
severity = "suggested"
```

```bash
habit-hooks --file src/billing.py --config ci.toml
```

🖥️ ✅
```text
── too-many-parameters (1 issue) ──

The following function definitions have more than 3 parameters:

src/billing.py:2
    bill(...) has 4 parameters

Bundle related arguments into an object.
```

## The installed command composes without its bin dir on PATH

The installed `habit-hooks` console script shells out to its siblings
`habit-sensors` and `habit-mapper`. Invoked by absolute path with its own bin
directory stripped from `PATH`, it resolves those siblings relative to itself
rather than by bare name, so the pipeline still composes.

```bash
PATH=/usr/bin:/bin "$VIRTUAL_ENV/bin/habit-hooks" --file src/billing.py
```

🖥️ ❌ 1
```text
── too-many-parameters (1 issue) ──

The following function definitions have more than 3 parameters:

src/billing.py:2
    bill(...) has 4 parameters

Bundle related arguments into an object.
```

## Either stage's failure propagates

### An enforced smell fails the whole pipeline

`too-many-parameters` is `enforced`; the mapper exits 1, and that is the
pipeline's exit code.

```bash
habit-hooks --all | head -1
```

🖥️ ❌ 1
```text
── too-many-parameters (7 issues) ──
```

### A clean run exits 0 and prints the pass reminder

When the sensors find nothing, the mapper renders the clean guide and the
pipeline exits 0. This leaf overrides the sensor to emit an empty array.

📄.habit-hooks/generic/sensors/params.toml
```toml
command = "echo []"
```

```bash
habit-hooks --all
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.
```

### A failed sensor fails the pipeline and is coached, never rendered clean

Broken tooling can never report a clean run. A sensor that dies contributes no
findings of its own, but `habit-sensors` appends the reserved `incomplete-run`
finding so the mapper coaches the break instead of rendering the clean guide over
it (#88). The pipeline both exits non-zero and prints the failure on stdout — the
`✅` pass reminder never appears. This leaf overrides the sensor to crash without
printing findings; the failure notice still reaches stderr
([habit-sensors.spec.md](habit-sensors.spec.md)).

📄.habit-hooks/generic/sensors/params.toml
```toml
command = "echo 'params: boom' >&2; exit 7"
```

```bash
habit-hooks --all 2>/dev/null
```

🖥️ ❌ 1
```text
── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-sensors: sensor 'params' failed: echo 'params: boom' >&2; exit 7
params: boom
Fix the broken tool (its full diagnosis is on stderr) and re-run; do not treat this change as checked.
```

### A sensors stage that dies before writing is coached too, and exits 2

The case above needs `habit-sensors` to survive long enough to append the
reserved finding. A failure that kills the stage itself — here a configured
plugin nobody installed — leaves the pipe empty instead, and the mapper used to
read that as no findings and print the `✅`. It coaches the incomplete run from
its own side now. Both stages agree on exit 2: the tool broke, the code did not
([habit-mapper.spec.md](habit-mapper.spec.md), #103).

📄.habit-hooks/config.toml
```toml
plugins = ["doesnotexist"]
```

```bash
habit-hooks --all 2>/dev/null
```

🖥️ ❌ 2
```text
── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-mapper: nothing arrived on stdin — the sensors stage exited before it wrote any findings
Fix the broken tool (its full diagnosis is on stderr) and re-run; do not treat this change as checked.
```

### A failed sensor and a working one both report, and the run stays incomplete

A break in one sensor does not hide what the others found: the working sensor's
findings are coached as usual, and the reserved `incomplete-run` finding is
appended after them so the same run is never mistaken for clean (#88). Here
`params` reports a real `too-many-parameters` finding while `broken` crashes.

📄.habit-hooks/generic/config.toml
```toml
sensors = ["params", "broken"]
```

📄.habit-hooks/generic/sensors/broken.toml
```toml
command = "echo 'boom' >&2; exit 1"
```

```bash
habit-hooks --file src/billing.py 2>/dev/null
```

🖥️ ❌ 1
```text
── too-many-parameters (1 issue) ──

The following function definitions have more than 3 parameters:

src/billing.py:2
    bill(...) has 4 parameters

Bundle related arguments into an object.

── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-sensors: sensor 'broken' failed: echo 'boom' >&2; exit 1
boom
Fix the broken tool (its full diagnosis is on stderr) and re-run; do not treat this change as checked.
```
