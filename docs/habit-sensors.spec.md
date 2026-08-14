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
files = ["**"]
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
files = ["**"]
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
files = ["**"]
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
files = ["**"]
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
files = ["**"]
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
files = ["**"]
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
files = ["**"]
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
files = ["**"]
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
carry. Both ends are quoted and the middle is counted — a Python traceback
names its exception on its last line, so quoting only the opening would drop
the one line that says what broke.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
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
habit-sensors --all 2>&1 >/dev/null | sed -n '2p;12p;22p'
```

🖥️ ❌ 1
```text
1
... 180 lines omitted ...
200
```

### A broken sensor fails the run; the rest still report

A spawn failure or a non-zero exit from a sensor's tool yields zero findings for
that sensor, a stderr notice naming it, and exit 1. The sibling sensors still
report — a broken tool is a failed run, never a clean one. A failed run also
appends the reserved `incomplete-run` finding to the pipe, so the mapper coaches
the break instead of rendering clean over it (#88).

Naming the sensor and its command says *what* broke, never *why*, so whatever
the tool wrote to stderr is carried into the notice — the same way a failing
transformer's own message is. Here that is the real case that prompted it: a Node
sensor naming the package it could not `require`. The one failure answered in
habit-hooks' own words instead is a command nobody installed, where the tool
never ran and so has no words of its own (#114).

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
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
command = "echo \"Error: Cannot find module 'ts-morph'\" >&2; exit 1"
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ❌ 1
```json
[
  "warning-comment",
  "incomplete-run"
]
```

🚨
```text
habit-sensors: sensor 'broken' failed: echo "Error: Cannot find module 'ts-morph'" >&2; exit 1
Error: Cannot find module 'ts-morph'
```

### A failed run is coached

A failed sensor contributes no findings of its own, so nothing on the pipe would
tell the mapper the run broke — it would see `[]` and render the clean guide over
broken tooling (#88). The runner therefore appends one reserved `incomplete-run`
finding whenever the run failed, carrying each failure notice as an issue's
`content`. It is appended after every transformer has run, so a snooze can never
mute it; the mapper coaches it like any enforced smell
([habit-mapper.spec.md](habit-mapper.spec.md)).

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["broken"]
```

📄.habit-hooks/generic/sensors/broken.toml
```toml
command = "echo 'boom' >&2; exit 1"
```

```bash
habit-sensors --all | jq -c '.[] | select(.smell=="incomplete-run") | {smell, contents: [.issues[].details.content]}'
```

🖥️ ❌ 1
```json
{"smell":"incomplete-run","contents":["habit-sensors: sensor 'broken' failed: echo 'boom' >&2; exit 1\nboom"]}
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
files = ["**"]
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
  "warning-comment",
  "incomplete-run"
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
files = ["**"]
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
a half-scan as a whole one. The dropped findings leave only the reserved
`incomplete-run` marker on the pipe, so the run reads as broken, never clean (#88).

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**"]
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
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
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
files = ["**"]
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
files = ["**"]
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
  "warning-comment",
  "incomplete-run"
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

The failed run also appends the reserved `incomplete-run` finding (#88); this
case filters it out to keep the focus on the untransformed findings passing
through — the marker's own shape is asserted under *A failed run is coached*.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
files = ["**"]
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
habit-sensors --all | jq -c '[.[] | select(.smell != "incomplete-run") | .issues[].key]'
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
files = ["**"]
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
  "warning-comment",
  "incomplete-run"
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
files = ["**"]
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
files = ["**"]
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

🖥️ ❌ 2

🚨
```text
habit-sensors: no transformer 'nope' in ['generic'] or the core
```

## Config is validated

A key the config loader consumes nothing for is a typo or a documented-but-dead
key. The runner rejects it by name at load time rather than ignoring it, so a
misspelling can never silently do nothing.

### A misspelled config key is caught by name

`severty` is not a `[smells.<name>]` field, so the run stops before any sensor
runs and names the offending key and the section it sits in.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]

[smells.duplicated-code]
severty = "suggested"
```

```bash
habit-sensors --all
```

🖥️ ❌ 2

🚨
```text
habit-sensors: unknown config key 'severty' in [smells.duplicated-code]; known keys: disabled, guide, severity
```

## Plugin recommendation

When the project clearly uses a language no active plugin covers, the runner
prints a **non-fatal** hint to stderr naming the plugin. The hint never changes
the findings on stdout nor the exit code; it is suppressed for any language an
active plugin already declares.

Installing a plugin does not switch it on — a plugin runs only once `plugins` in
`.habit-hooks/config.toml` names it — so every hint names that step. A plugin
that is nowhere on the machine is hinted as ``consider `pip install
habit-hooks-python`, then add "python" to `plugins` in .habit-hooks/config.toml``;
one that is already there drops the install half and asks only for the config
line, so following a hint is never a loop.

### A used language whose plugin is not enabled is recommended on stderr

Here only `generic` is active (it declares no language), and a `*.py` file is in
scope. The `python` plugin is on hand — vendored below, exactly as an installed
`habit-hooks-python` would be — but `plugins` does not name it, so the hint asks
for the one step that is missing. The runner still exits per its findings (exit
0, the finding on stdout).

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.py"]
```

📄.habit-hooks/python/config.toml
```toml
language = "python"
sensors  = []
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
habit-sensors: detected python; the python plugin is installed but not enabled — add "python" to `plugins` in .habit-hooks/config.toml
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
with no `tsconfig.json` and no `*.ts`/`*.tsx` in scope, no TypeScript
recommendation prints. The Python one still does, from the same run, which is
what makes this case a discriminator rather than an empty assertion.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.py"]
```

📄.habit-hooks/python/config.toml
```toml
language = "python"
sensors  = []
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
habit-sensors: detected python; the python plugin is installed but not enabled — add "python" to `plugins` in .habit-hooks/config.toml
```

### A tsconfig.json signals TypeScript

A `tsconfig.json` is a real TypeScript signal, so with no active plugin declaring
`typescript` the runner recommends the plugin.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.py"]
```

📄.habit-hooks/typescript/config.toml
```toml
language = "typescript"
sensors  = []
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
habit-sensors: detected typescript; the typescript plugin is installed but not enabled — add "typescript" to `plugins` in .habit-hooks/config.toml
```

## Version and argument validation

`--version` prints the installed distribution's version so a bug report can name
it, and it is answered before any config or git is touched. An invalid `--last`
is a usage error (exit 2), distinct from an enforced finding (exit 1), so a
mistyped count fails loudly instead of scanning everything.

### --version prints the distribution version

The exact number moves with each release, so this only pins the shape:
`habit-hooks vX.Y.Z` on stdout, exit 0.

```bash
habit-sensors --version | grep -qE '^habit-hooks v[0-9]+\.[0-9]+\.[0-9]+' && echo matched
```

🖥️ ✅
```text
matched
```

### --last rejects a non-positive count

`--last 0` scoped nothing and `--last -1` resolved to `HEAD~-1` and degraded to
the empty tree — both silently scanned the whole repository. A non-positive count
is now a usage error, exit 2, before any scope path is reached.

```bash
habit-sensors --last 0
```

🖥️ ❌ 2

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
files   = ["src/**"]
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

### `--file` surfaces a finding `--all` leaves snoozed

`--file` answers "tell me everything about this file, right now", so it sets the
snooze index aside — a standing exemption is a statement about the backlog, not
about the file you named (#55). `src/a.txt` is snoozed, so `--all` filters its
finding out; `--file src/a.txt` reports it anyway. Only snoozing is bypassed, so
a project's own transformers are untouched.

📄src/a.txt
```text
a
```

📄.habit-hooks/snooze.json
```json
["src/a.txt"]
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

```bash
habit-sensors --file src/a.txt | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/a.txt"]
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

### A `--file` in a project that names no source at all says so

With no `[files]` anywhere — the documented default `plugins = ["generic"]`,
which declares no source — there is no section for the named file to be *outside*
of, so the notice names the missing setting instead of a phantom one. The hook
behind `--file` still fires on every edit, so this is not an error: exit 0, an
empty findings array on stdout, and the one line that says why on stderr.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄src/a.txt
```text
a
```

```bash
habit-sensors --file src/a.txt | jq '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

🚨
```text
habit-sensors: --file 'src/a.txt': no [files] are configured — name what to scan in .habit-hooks/config.toml; nothing scanned
```

### A project that names no source scans nothing

Discovery is opt-in, not a denylist. With no `[files]` from the project and none
from its plugins — the documented default `plugins = ["generic"]` — the scope is
empty, so a default install sweeps nobody's `node_modules`, `.venv` or `.git`
looking for source (#97). A run that measured nothing must never read as clean,
so it says why on stderr and leaves stdout a valid empty findings array. This
case restates the default config to drop the section's `files`, so the project
and its lone `generic` plugin both name no source.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄src/a.txt
```text
a
```

📄node_modules/pkg/vendored.txt
```text
somebody else's code
```

```bash
habit-sensors --all
```

🖥️ ✅
```json
[]
```

🚨
```text
habit-sensors: no [files] are configured — name what to scan in .habit-hooks/config.toml; nothing scanned
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
must not show up as one of the branch's own changes. A scoped run now also
measures untracked and staged work (#92), so `[files] = ["src/**"]` keeps this
config out of what the sensors see — exactly as a real project's `[files]` does.

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
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

#### Untracked and staged work in progress is still measured

The file most likely to carry a fresh smell is the one just written — new, or
staged for a commit that has not happened yet. `git diff` names neither, so a
scope built on it alone would report clean over the very work under review (#92).
Here the branch stages an edit to `src/a.txt` and adds a brand-new `src/new.txt`
without committing either; both reach the sensor.

```bash
git checkout -q -b feature &&
  printf 'more\n' >> src/a.txt &&
  git add src/a.txt &&
  printf 'brand new\n' > src/new.txt
```

```bash
habit-sensors --branch main | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/a.txt","src/new.txt"]
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

🖥️ ❌ 2

🚨
```text
habit-sensors: base ref 'main' does not resolve in this checkout — set [scope] branchBase to a ref it has
```

### A project with no `files` of its own inherits its plugins'

`files` is the one root key a plugin supplies a default for: a project that names
none scans what its plugins call source — every active plugin's `files`, in
`plugins` order. A plugin that declares none (`generic` in the fixture above) is
stating no opinion, not "everything", so a project whose plugins all stay silent
scans nothing at all — discovery is opt-in (#97).

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
