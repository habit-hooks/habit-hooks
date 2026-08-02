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

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
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

### A failed sensor fails the pipeline, even when the mapper is clean

Broken tooling can never report a clean run. A sensor that dies contributes no
findings, so the mapper sees an empty array and renders the clean guide — but
`habit-sensors` exits non-zero for the failure ([habit-sensors.spec.md](habit-sensors.spec.md)),
and the pipeline propagates that. This leaf overrides the sensor to crash without
printing findings.

📄.habit-hooks/generic/sensors/params.toml
```toml
command = "echo 'params: boom' >&2; exit 7"
```

```bash
habit-hooks --all
```

🖥️ ❌ 1
