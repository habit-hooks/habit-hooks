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

### A broken sensor fails the run; the rest still report

A spawn failure or a non-zero exit from a sensor's tool yields zero findings for
that sensor, a stderr notice naming it, and exit 1. The sibling sensors still
report — a broken tool is a failed run, never a clean one.

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
command = "this-tool-does-not-exist"
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
habit-sensors: sensor 'broken' failed: this-tool-does-not-exist
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
habit-sensors: transformer 'snooze-until-changed' failed: ${python} -m habit_hooks.snooze --until-changed
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
| `--branch [base]` | changed vs `base` (default `scope.branchBase`) |
| `--last <n>` | changed in the last `n` commits |
| `--since <ref>` | changed since a commit |
| `--config <path>` | use an explicit config file |
| (none) | `scope.changedOnly` → uncommitted; else `scope.autoBranchOffMain` → vs base unless on `scope.mainBranch`; else all |

A git-mode flag run outside a git repository errors; the config-derived modes
fall back to scanning every file instead.

### --file scopes `${files}` to one file

`--file` narrows `${files}` to the one named path, so the sensor only sees
`src/a.txt` even though `src/b.txt` also exists.

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
