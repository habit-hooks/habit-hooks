# habit-sensors

`habit-sensors` is the **extract-and-transform runner**: it assembles the
configured sensors and transformers into a pipeline, runs it over the files in
scope, and prints a `{smell, language?, details, issues}` findings array on
stdout — the input to `habit-mapper`. `habit-hooks` is just `habit-sensors $ARGS
| habit-mapper`.

This document specifies the runner's **behaviour** only: how sibling sensors
combine, how a plugin stamps its language, how the transformer chain runs, how
plugins compose, how a broken sensor is handled, and how scope flags pick the
files. The ETL model, plugins, and override resolution it rests on are described
in [architecture.md](architecture.md); the finding shape every step speaks is
the contract in [sensor-interface.spec.md](sensor-interface.spec.md); the TOML
config that wires it up is in [config.md](config.md).

## Sensors combine

### Sibling sensors concatenate in listed order

The runner runs each sensor in a plugin and concatenates their findings in the
order the plugin's `sensors` list names them.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha", "beta"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "cat ${dir}/alpha.json"
```

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"warning-comment","details":{},"issues":[]}]
```

📄.habit-hooks/generic/sensors/beta.toml
```toml
command = "cat ${dir}/beta.json"
```

📄.habit-hooks/generic/sensors/beta.json
```json
[{"smell":"oversized-file","details":{},"issues":[]}]
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ✅
```json
[
  "warning-comment",
  "oversized-file"
]
```

### A plugin stamps its declared language; the name need not match

A plugin *declares* the language it speaks in its `config.toml`, and the runner
stamps that onto the plugin's findings — even when the plugin's name is the tool
(`ruff`) rather than the language (`python`).

📄.habit-hooks/config.toml
```toml
plugins = ["ruff"]
```

📄.habit-hooks/ruff/config.toml
```toml
language = "python"
sensors  = ["check"]
```

📄.habit-hooks/ruff/sensors/check.toml
```toml
command = "cat ${dir}/out.json"
```

📄.habit-hooks/ruff/sensors/out.json
```json
[{"smell":"too-many-parameters","details":{},"issues":[]}]
```

```bash
habit-sensors --all | jq '[.[].language]'
```

🖥️ ✅
```json
[
  "python"
]
```

## Transformers reshape

### A transformer rewrites what it handles and passes the rest through

A transformer receives the whole findings array on stdin and returns a new one.
Here it tags every `warning-comment` finding and leaves the `oversized-file`
finding untouched — the pass-through rule that lets transformers compose freely.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["tag"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha", "beta"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "cat ${dir}/alpha.json"
```

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"warning-comment","details":{},"issues":[]}]
```

📄.habit-hooks/generic/sensors/beta.toml
```toml
command = "cat ${dir}/beta.json"
```

📄.habit-hooks/generic/sensors/beta.json
```json
[{"smell":"oversized-file","details":{},"issues":[]}]
```

📄.habit-hooks/generic/transformers/tag.toml
```toml
command = "jq 'map(if .smell == \"warning-comment\" then .details.tagged = true else . end)'"
```

```bash
habit-sensors --all | jq 'map({smell, details})'
```

🖥️ ✅
```json
[
  {
    "smell": "warning-comment",
    "details": {
      "tagged": true
    }
  },
  {
    "smell": "oversized-file",
    "details": {}
  }
]
```

### The transformer chain runs left to right

When a node lists several transformers, the runner pipes the findings through
them in listed order, so each sees the previous one's output.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["first", "second"]
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
[{"smell":"warning-comment","details":{"steps":[]},"issues":[]}]
```

📄.habit-hooks/generic/transformers/first.toml
```toml
command = "jq 'map(.details.steps += [\"first\"])'"
```

📄.habit-hooks/generic/transformers/second.toml
```toml
command = "jq 'map(.details.steps += [\"second\"])'"
```

```bash
habit-sensors --all | jq '.[0].details.steps'
```

🖥️ ✅
```json
[
  "first",
  "second"
]
```

### Snooze runs by default, with no `transformers` key at all

`transformers` defaults to `["snooze"]`, so a project's checked-in snooze index
takes effect without any wiring. The config below never mentions transformers,
yet the snoozed key is dropped and the other survives.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
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
[{"smell":"oversized-file","details":{},"issues":[{"key":"src/big.py","details":{"file":"src/big.py"}},{"key":"src/ok.py","details":{"file":"src/ok.py"}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/big.py"]
```

```bash
habit-sensors --all | jq '[.[].issues[].key]'
```

🖥️ ✅
```json
[
  "src/ok.py"
]
```

### The core supplies `snooze` when no plugin ships it

A default that a plugin owned could be switched off by dropping that plugin.
`snooze` is a core console script, so the core supplies its transformer spec as
the last link in the resolution chain — the same fallback the mapper uses for
its baseline guides. Here `generic` is not listed and no plugin ships a
transformer, and the default still resolves.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
```

📄.habit-hooks/python/config.toml
```toml
language = "python"
sensors  = ["p"]
```

📄.habit-hooks/python/sensors/p.toml
```toml
command = "cat ${dir}/p.json"
```

📄.habit-hooks/python/sensors/p.json
```json
[{"smell":"too-many-parameters","details":{},"issues":[{"key":"src/a.py","details":{"file":"src/a.py"}},{"key":"src/b.py","details":{"file":"src/b.py"}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/a.py"]
```

```bash
habit-sensors --all | jq '[.[].issues[].key]'
```

🖥️ ✅
```json
[
  "src/b.py"
]
```

### The core also supplies the opt-in `snooze-until-changed`

The core ships a second snooze transformer whose exemptions lapse as soon as the
file changes ([habit-snooze.spec.md](habit-snooze.spec.md)); a project opts in
by naming it. Both keys below are snoozed and both files are committed, but only
`src/big.py` is then edited — so only its issue comes back.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["snooze-until-changed"]
files        = ["src/**"]
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
[{"smell":"oversized-file","details":{},"issues":[{"key":"src/big.py","details":{"file":"src/big.py"}},{"key":"src/ok.py","details":{"file":"src/ok.py"}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/big.py", "src/ok.py"]
```

📄src/big.py
```python
VALUES = [1]
```

📄src/ok.py
```python
VALUES = [2]
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add src &&
  git commit -q -m baseline &&
  printf 'VALUES.append(2)\n' >> src/big.py
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/big.py"]
```

### A project overrides the default by listing `transformers` itself

The default is a default, not a policy: naming `transformers` replaces it
wholesale, so a project can drop snooze or order it against its own steps. Here
the list omits `snooze`, and the snoozed key comes through untouched.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = []
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
[{"smell":"oversized-file","details":{},"issues":[{"key":"src/big.py","details":{"file":"src/big.py"}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/big.py"]
```

```bash
habit-sensors --all | jq '[.[].issues[].key]'
```

🖥️ ✅
```json
[
  "src/big.py"
]
```

## Plugins compose

### Active plugins concatenate; dropping one drops its findings

The root `plugins` list decides which plugins run, in order. Here `python` is
listed and `generic` is not, so only `python`'s sensors run and `generic`'s
findings never appear.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["g"]
```

📄.habit-hooks/generic/sensors/g.toml
```toml
command = "cat ${dir}/g.json"
```

📄.habit-hooks/generic/sensors/g.json
```json
[{"smell":"duplicated-code","details":{},"issues":[]}]
```

📄.habit-hooks/python/config.toml
```toml
language = "python"
sensors  = ["p"]
```

📄.habit-hooks/python/sensors/p.toml
```toml
command = "cat ${dir}/p.json"
```

📄.habit-hooks/python/sensors/p.json
```json
[{"smell":"too-many-parameters","details":{},"issues":[]}]
```

```bash
habit-sensors --all | jq '[.[] | [.smell, .language]]'
```

🖥️ ✅
```json
[
  [
    "too-many-parameters",
    "python"
  ]
]
```

## Failure is not false-clean

### A sensor that dies loudly is quoted, not transcribed

A part's own complaint is the actionable half of a notice, but habit-hooks writes
into a coding agent's context: a tool that dies mid-warning-storm can produce
megabytes, and transcribing it would crowd out the diagnosis it is there to
carry. The opening lines are quoted and the remainder is counted.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["shouty"]
```

📄.habit-hooks/generic/sensors/shouty.toml
```toml
command = "seq 200 >&2; exit 1"
```

```bash
habit-sensors --all 2>&1 >/dev/null | wc -l | tr -d ' '
```

🖥️ ❌ 1
```text
22
```

### A broken sensor fails the run; the rest still report

A spawn failure or a non-zero exit from a sensor's tool yields zero findings for
that sensor, a stderr notice naming it, and exit 1. The sibling sensors still
report — a broken tool is a failed run, never a clean one.

Naming the sensor and its command says *what* broke, never *why*, so whatever
the tool wrote to stderr is carried into the notice — the same way a failing
transformer's own message is. Here that is the shell reporting a tool nobody
installed; for the real case that prompted it, a Node sensor naming the package
it could not `require`.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok", "broken"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "cat ${dir}/ok.json"
```

📄.habit-hooks/generic/sensors/ok.json
```json
[{"smell":"warning-comment","details":{},"issues":[]}]
```

📄.habit-hooks/generic/sensors/broken.toml
```toml
command = "echo 'this-tool-does-not-exist: command not found' >&2; exit 127"
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ❌ 1
```json
[
  "warning-comment"
]
```

🚨
```text
habit-sensors: sensor 'broken' failed: echo 'this-tool-does-not-exist: command not found' >&2; exit 127
this-tool-does-not-exist: command not found
```

### A sensor that exits non-zero with nothing on stdout is a failure

Exit 1 is how a linter says "I found things", so a sensor is allowed it — but
only alongside the findings that justify it. With stdout empty the two readings
collapse: "exited 1 with findings" and "exited 1 because it died before printing
anything" become the same run, and the empty stdout parses as no findings. That
is the false-clean this whole section exists to prevent, so the sensor fails.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok", "crashed"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "cat ${dir}/ok.json"
```

📄.habit-hooks/generic/sensors/ok.json
```json
[{"smell":"warning-comment","details":{},"issues":[]}]
```

📄.habit-hooks/generic/sensors/crashed.toml
```toml
command = "exit 1"
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ❌ 1
```json
[
  "warning-comment"
]
```

🚨
```text
habit-sensors: sensor 'crashed' failed: exit 1
```

### A sensor that exits 1 with findings is a tool reporting what it found

The counterpart to the case above, and the reason a non-zero exit is not simply
refused: `ruff` and `eslint` both exit 1 precisely *because* they found
something, and their findings are on stdout where they belong. Exiting 1 is the
tool's convention, not its distress signal, so the findings report and the run
passes.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["linter"]
```

📄.habit-hooks/generic/sensors/linter.toml
```toml
command = "cat ${dir}/linter.json; exit 1"
```

📄.habit-hooks/generic/sensors/linter.json
```json
[{"smell":"loose-equality","details":{},"issues":[{"key":"src/a.ts","details":{"file":"src/a.ts"}}]}]
```

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ✅
```json
["loose-equality"]
```

### A sensor that exits outside 0/1 fails even with findings on stdout

Exit 1 is the only non-zero code a tool gets to mean something by; anything
beyond it is the tool saying it broke. Findings printed on the way out do not
buy it back — a crash that got as far as writing has no way to say how much of
what it wrote it stands behind, so the run refuses the lot rather than reporting
a half-scan as a whole one.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["partial"]
```

📄.habit-hooks/generic/sensors/partial.toml
```toml
command = "cat ${dir}/partial.json; exit 2"
```

📄.habit-hooks/generic/sensors/partial.json
```json
[{"smell":"oversized-file","details":{},"issues":[{"key":"src/a.py","details":{"file":"src/a.py"}}]}]
```

```bash
habit-sensors --all | jq -c '.'
```

🖥️ ❌ 1
```json
[]
```

🚨
```text
habit-sensors: sensor 'partial' failed: cat ${dir}/partial.json; exit 2
```

### A sensor that exits 0 with nothing on stdout is clean

Silence is judged by the exit code that came with it. Exit 0 is the sensor
explicitly claiming it ran to completion, and a sensor that adds no findings is
exactly what a clean one does — so unlike a transformer, whose silence would
discard everything the sensors found, a quiet successful sensor is trusted.
Every bundled sensor prints `[]` rather than relying on this; it is here so a
third-party one that does not is still readable.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["quiet"]
```

📄.habit-hooks/generic/sensors/quiet.toml
```toml
command = "true"
```

```bash
habit-sensors --all | jq -c '.'
```

🖥️ ✅
```json
[]
```

### A broken transformer fails the run and keeps the findings it was given

A transformer that dies must never be able to shrink the run. Empty stdout would
otherwise parse as "no findings", so a crash would discard everything the
sensors found and report a clean pass — the failure mode that matters most, now
that `snooze` runs by default. A transformer that exits non-zero, or prints
nothing, is therefore a failed run whose findings pass through **untransformed**.

Unlike a sensor, a transformer has no convention for exiting non-zero: it must
exit 0 and print its array, printing `[]` when it drops everything.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["boom"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "cat ${dir}/ok.json"
```

📄.habit-hooks/generic/sensors/ok.json
```json
[{"smell":"warning-comment","details":{},"issues":[{"key":"src/x.py","details":{}}]}]
```

📄.habit-hooks/generic/transformers/boom.toml
```toml
command = "exit 1"
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ❌ 1
```json
[
  "warning-comment"
]
```

🚨
```text
habit-sensors: transformer 'boom' failed: exit 1
```

### A failing transformer's own message reaches the user

Naming the transformer and its command says *what* broke, never *why* — and the
why is often the only actionable part. Whatever the transformer wrote to stderr
is carried into the notice, so a pipeline user reads the diagnosis instead of
guessing at it.

The real case: `snooze-until-changed` exits non-zero when `[scope] branchBase`
is missing from the checkout ([habit-snooze.spec.md](habit-snooze.spec.md)), and
the setting that fixes it is named in *its* message, not the runner's.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["snooze-until-changed"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "cat ${dir}/ok.json"
```

📄.habit-hooks/generic/sensors/ok.json
```json
[{"smell":"oversized-file","details":{},"issues":[{"key":"src/notes.txt","details":{"file":"src/notes.txt"}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/notes.txt"]
```

📄src/notes.txt
```text
one line
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add src &&
  git commit -q -m baseline &&
  git branch -m main trunk
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ❌ 1
```json
["src/notes.txt"]
```

🚨
```text
habit-sensors: transformer 'snooze-until-changed' failed: ${python} -m habit_hooks.snooze --until-changed ${config}
habit-snooze: base ref 'main' does not resolve in this checkout — set [scope] branchBase to a ref it has
```

### A transformer that prints nothing is a failure, not an empty run

Exiting 0 is not enough — a transformer killed mid-write, or one whose command
silently produces no output, also has nothing trustworthy to say. Only an
explicit array counts, so `[]` still means "everything dropped" and silence
means "broken".

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["mute"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "cat ${dir}/ok.json"
```

📄.habit-hooks/generic/sensors/ok.json
```json
[{"smell":"warning-comment","details":{},"issues":[{"key":"src/x.py","details":{}}]}]
```

📄.habit-hooks/generic/transformers/mute.toml
```toml
command = "true"
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ❌ 1
```json
[
  "warning-comment"
]
```

🚨
```text
habit-sensors: transformer 'mute' failed: true
```

### A transformer that drops everything prints `[]` and is trusted

The counterpart to the two cases above: an explicit empty array is a legitimate
result, so a transformer is still free to clear the run — that is exactly what
`snooze` does when every issue is snoozed.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["clear"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "cat ${dir}/ok.json"
```

📄.habit-hooks/generic/sensors/ok.json
```json
[{"smell":"warning-comment","details":{},"issues":[{"key":"src/x.py","details":{}}]}]
```

📄.habit-hooks/generic/transformers/clear.toml
```toml
command = "jq '[]'"
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ✅
```json
[]
```

### A transformer no plugin and no core ships fails by name

Resolution walks the configured plugins and then the core. When none supplies
the named part the run stops with an error saying where it looked, rather than
carrying on with a step the project asked for and did not get.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
transformers = ["nope"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["ok"]
```

📄.habit-hooks/generic/sensors/ok.toml
```toml
command = "echo []"
```

```bash
habit-sensors --all
```

🖥️ ❌ 1

🚨
```text
habit-sensors: no transformer 'nope' in ['generic'] or the core
```

## Plugin recommendation

When the project clearly uses a language no active plugin covers, the runner
prints a **non-fatal** hint to stderr naming the plugin to install. The hint
never changes the findings on stdout nor the exit code; it is suppressed for any
language an active plugin already declares.

### A used language with no active plugin is recommended on stderr

Here only `generic` is active (it declares no language), and a `*.py` file is in
scope. The runner still exits per its findings (exit 0, the finding on stdout),
and prints the Python recommendation to stderr.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.py"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["clean"]
```

📄.habit-hooks/generic/sensors/clean.toml
```toml
command = "cat ${dir}/clean.json"
```

📄.habit-hooks/generic/sensors/clean.json
```json
[]
```

📄app.py
```python
x = 1
```

```bash
habit-sensors --all | jq '.'
```

🖥️ ✅
```json
[]
```

🚨
```text
habit-sensors: detected python; consider `pip install habit-hooks-python`
```

### An already-active plugin's language is not recommended

The `python` plugin is active and declares `python`, so the same `*.py` file in
scope produces **no** recommendation — stderr is empty (captured here as stdout).

📄.habit-hooks/config.toml
```toml
plugins = ["python"]
files   = ["**/*.py"]
```

📄.habit-hooks/python/config.toml
```toml
language = "python"
sensors  = ["clean"]
```

📄.habit-hooks/python/sensors/clean.toml
```toml
command = "cat ${dir}/clean.json"
```

📄.habit-hooks/python/sensors/clean.json
```json
[]
```

📄app.py
```python
x = 1
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
```

### A package.json alone does not signal TypeScript

A non-TypeScript project may carry a `package.json` only to configure a Node tool
(a linter, a duplication detector). That alone is **not** a TypeScript signal —
with no `tsconfig.json` and no `*.ts`/`*.tsx` in scope, no recommendation prints.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.py"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["clean"]
```

📄.habit-hooks/generic/sensors/clean.toml
```toml
command = "cat ${dir}/clean.json"
```

📄.habit-hooks/generic/sensors/clean.json
```json
[]
```

📄package.json
```json
{ "name": "demo", "devDependencies": { "jscpd": "^4" } }
```

📄app.py
```python
x = 1
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
habit-sensors: detected python; consider `pip install habit-hooks-python`
```

### A tsconfig.json signals TypeScript

A `tsconfig.json` is a real TypeScript signal, so with no active plugin declaring
`typescript` the runner recommends the plugin.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.py"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["clean"]
```

📄.habit-hooks/generic/sensors/clean.toml
```toml
command = "cat ${dir}/clean.json"
```

📄.habit-hooks/generic/sensors/clean.json
```json
[]
```

📄tsconfig.json
```json
{ "compilerOptions": { "strict": true } }
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
habit-sensors: detected typescript; consider `pip install habit-hooks-typescript`
```

## Scope

`habit-sensors` first picks the files the leaf sensors see, then expands
`${files}` to them. The scope flags are mutually exclusive; with none, the scope
comes from the `[scope]` config.

| Flag | Scope |
|------|-------|
| `--all` | every file |
| `--file <path>` | a single file |
| `--branch [base]` | changed since this branch left `base` (default `scope.branchBase`) |
| `--last <n>` | changed in the last `n` commits |
| `--since <ref>` | changed since a commit |
| `--config <path>` | use an explicit config file |
| (none) | `scope.changedOnly` → uncommitted; else `scope.autoBranchOffMain` → vs base unless on `scope.mainBranch`; else all |

A git-mode flag run outside a git repository errors; the config-derived modes
fall back to scanning every file instead. A ref a *real* repository does not have
is an error too: git answers a ref it never heard of with an empty diff, and a
run that scanned nothing would report every sensor clean.

However the paths were picked, the same two narrowings apply before any sensor
sees them:

- **a path the work tree no longer has is dropped** — every git diff names the
  files a branch deleted, and a deleted file has no smells left to find;
- **what survives must match `[files]`** — so one setting says what this project
  considers source, whether the run came from a flag or from git.

Every case below shares this fixture: a sensor that reports back exactly the
files it was handed.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["echo-files"]
```

📄.habit-hooks/generic/sensors/echo-files.toml
```toml
command = "jq -n --args '[{smell: \"warning-comment\", details: {}, issues: ($ARGS.positional | map({key: ., details: {file: .}}))}]' ${files}"
```

### --file scopes `${files}` to one file

`--file` narrows `${files}` to the one named path, so the sensor only sees
`src/a.txt` even though `src/b.txt` also exists.

📄src/a.txt
```text
a
```

📄src/b.txt
```text
b
```

```bash
habit-sensors --file src/a.txt | jq '[.[].issues[].key]'
```

🖥️ ✅
```json
[
  "src/a.txt"
]
```

### A `--file` the project does not count as source says so

`[files]` narrows every mode, `--file` included — the hook behind it fires on
each edited file, including the ones a project rightly does not scan. That is
not an error, so the run still exits 0; but it scanned nothing, and a run that
measured nothing must never be indistinguishable from a clean one. It says which
file and why, on stderr, leaving stdout a valid empty findings array.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
```

📄src/a.txt
```text
a
```

📄pnpm-lock.yaml
```text
lockfile
```

```bash
habit-sensors --file pnpm-lock.yaml | jq '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

🚨
```text
habit-sensors: --file 'pnpm-lock.yaml' is outside [files]; nothing scanned
```

### Git-derived scopes

`--branch`, `--since` and the `[scope]` defaults all ask git one question: what
has this branch changed since it left the base ref? It is measured from the
**merge base** of that ref and `HEAD`, so work someone else lands on the base
afterwards is never scanned as if it were yours.

Each case here builds its own repository. The spec harness runs every case in a
directory *inside* this project's checkout, so a case that skipped `git init`
would be answered about habit-hooks itself — and would go on to *rename its
branches*. `GIT_CEILING_DIRECTORIES` stops git's upward walk at the case
directory, so these cases can only ever see the repository they build. A real
project needs no such thing.

`.habit-hooks/` is left untracked on purpose: a fixture a case rewrites later
must not show up as one of the branch's own changes.

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

📄src/a.txt
```text
a
```

📄src/b.txt
```text
b
```

📄pnpm-lock.yaml
```text
lockfile
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add src pnpm-lock.yaml &&
  git commit -q -m baseline
```

#### A file the branch deleted is not scanned

The branch edits one file and deletes another. Git names both, as it must — but
only the surviving file can still be read, so only it reaches the sensor.

```bash
git checkout -q -b feature &&
  printf 'more\n' >> src/a.txt &&
  git rm -q src/b.txt &&
  git commit -q -am "grow a, drop b"
```

```bash
git diff --name-only main
```

🖥️ ✅
```text
src/a.txt
src/b.txt
```

```bash
habit-sensors --branch main | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/a.txt"]
```

#### `[files]` narrows a branch's changes too

A branch that bumps a lockfile alongside its source must not be scored on the
lockfile: `[files]` already says what this project counts as source, and it says
so for every mode. Without it the run would report a smell the consumer could
only silence by snoozing a file nobody will ever refactor.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
```

```bash
git checkout -q -b feature &&
  printf 'more\n' >> src/a.txt &&
  printf 'bumped\n' >> pnpm-lock.yaml &&
  git commit -q -am "bump the lockfile"
```

```bash
habit-sensors --branch main | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/a.txt"]
```

#### Work landed on the base ref afterwards is not this branch's

The comparison starts at the merge base, not at the tip of the base ref. Here
the branch edits `src/a.txt` while somebody else lands `src/b.txt` on `main`:
scoping in their file would fail this branch's gate on debt it never went near.

```bash
git checkout -q -b feature &&
  printf 'more\n' >> src/a.txt &&
  git commit -q -am "this branch touches a" &&
  git checkout -q main &&
  printf 'moved on\n' >> src/b.txt &&
  git commit -q -am "main moves on without us" &&
  git checkout -q feature
```

```bash
habit-sensors --branch main | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/a.txt"]
```

#### A base ref this checkout cannot resolve fails the run

A shallow CI checkout never fetched `main`; a project whose trunk is `master`
never had one; a typo in `[scope] branchBase` names one that was never there.
Each would diff against nothing, scan nothing, and report clean — the silent
green that makes a scoped run untrustworthy. So the run fails instead, naming
the ref and the setting that named it.

The base branch is renamed here while `[scope] branchBase` stays at its `main`
default, which is also what proves this case owns its repository: habit-hooks'
own checkout does have `main`.

```bash
git branch -m main trunk
```

```bash
git rev-parse --verify --quiet 'main^{commit}'
```

🖥️ ❌ 1

```bash
habit-sensors --branch
```

🖥️ ❌ 1

🚨
```text
habit-sensors: base ref 'main' does not resolve in this checkout — set [scope] branchBase to a ref it has
```

### A project with no `files` of its own inherits its plugins'

`files` is the one root key a plugin supplies a default for: a project that names
none scans what its plugins call source — every active plugin's `files`, in
`plugins` order. A plugin that declares none (`generic` in the fixture above) is
stating no opinion, not "everything", so a project whose plugins all stay silent
still scans the whole tree.

📄.habit-hooks/config.toml
```toml
plugins = ["generic", "prose"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["echo-files"]
files   = ["src/**"]
```

📄.habit-hooks/prose/config.toml
```toml
sensors = []
files   = ["notes/**"]
```

📄src/a.txt
```text
a
```

📄notes/design.md
```text
design
```

📄pnpm-lock.yaml
```text
lockfile
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["notes/design.md","src/a.txt"]
```

### A project's own `files` replaces its plugins'

The project's answer is the authoritative one: naming `files` replaces the
plugins' defaults wholesale rather than adding to them, the same way naming
`transformers` does. Here the plugin says `src/**` and the project says
`notes/**`, and only the project's answer survives.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["notes/**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["echo-files"]
files   = ["src/**"]
```

📄src/a.txt
```text
a
```

📄notes/design.md
```text
design
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["notes/design.md"]
```
