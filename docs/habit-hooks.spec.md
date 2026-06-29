# habit-hooks

`habit-hooks` is the whole tool: the two stages composed over a Unix pipe,
`habit-sensors $ARGS | habit-mapper`. The arguments scope the sensors stage, the
findings flow through the pipe, and the mapper's exit code becomes the
pipeline's. This document specs only that composition — argument forwarding and
exit-code propagation; the stages' own behaviour lives in
[habit-sensors.spec.md](habit-sensors.spec.md) and
[habit-mapper.spec.md](habit-mapper.spec.md), and the big picture in
[architecture.md](architecture.md).

```bash
habit-hooks() { ../../habit-hooks "$@"; }
```

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
The following function definitions have more than 3 parameters:

src/billing.py:2
    bill(...) has 4 parameters

Bundle related arguments into an object.
```

## The mapper's exit code propagates

### An enforced smell fails the whole pipeline

`too-many-parameters` is `enforced`; the mapper exits 1, and that is the
pipeline's exit code.

```bash
habit-hooks --all | head -1
```

🖥️ ❌ 1
```text
The following function definitions have more than 3 parameters:
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
