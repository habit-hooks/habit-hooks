# 06. A repo cannot state the version of habit-hooks it needs

A project's `.habit-hooks/config.toml` says which plugins to run, what counts as
source, which transformers apply — everything except the one fact the rest of it
depends on: **which version of habit-hooks can read it.** There is no key for
that, so a project that needs 1.1.0 has to enforce the floor outside the config,
by hand, in every place that installs the tool.

Two projects, two failure modes, both observed:

- **OpenBoard** hand-syncs the same version literal in **three** places —
  `.github/workflows/deploy.yml` and two separate lines of its `CLAUDE.md` — with
  a comment in the workflow asking whoever edits one to remember the other two.
  It works exactly as long as nobody forgets.
- **3dmaze** installs unpinned, per machine. A teammate on an older build gets
  different findings from the same commit, and nothing says so.

The sharp edge is a project *migrating* its config forward. Point a 1.0.3 client
at a config that names a transformer only newer clients ship, and this is what
1.0.3 actually did (`~/.local/share/uv/tools/habit-hooks`, verbatim):

```text
$ habit-sensors --all ; echo $?
habit-sensors: no transformer 'snooze-until-merged' in ['generic']
1

$ habit-hooks --all ; echo $?          # the binary the git hook actually runs
habit-sensors: no transformer 'snooze-until-merged' in ['generic']
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
0
```

The runner was right and the wrapper overrode it: a green tick and exit 0 on a
run that never happened. **That wrapper bug is fixed on current main** (#88 —
either stage failing fails the run, and an empty pipe is coached as
`incomplete-run`), and the fix is what makes a version floor worth having: a
floor is only enforceable if failing to meet it cannot be papered over
downstream. The keeper case below pins it.

The same 1.0.3 client, given the floor key this finding asks for, ignores it
silently and exits 0 — an unknown root key was not rejected until #102. So
shipping `requires` does not retro-fit a good error onto old clients; on a client
new enough to reject unknown keys it fails loudly with the wrong message
(Today's first case), and on anything older it does nothing at all. That is an
argument for shipping it soon, not for shipping it differently.

**The spelling this finding proposes: a root `requires` key holding a PEP 440
specifier.**

```toml
requires = ">=1.1.0"
```

Why that, from [config.md](../config.md)'s own conventions: root keys are bare
lowercase nouns stating a whole-run fact (`plugins`, `transformers`, `files`), and
a version floor is exactly that shape — not a `[table]`, which the config reserves
for per-thing overrides (`[scope]`, `[sensors.*]`, `[smells.*]`). No namespace
prefix, because the file is habit-hooks' own and nothing else is being versioned
in it. A PEP 440 specifier string rather than a bare number, because habit-hooks
is a Python distribution whose version already comes from distribution metadata
(`habit-sensors --version` prints `habit-hooks vX.Y.Z`), so `>=1.1.0` and `~=1.1`
both mean what a Python packager expects without inventing syntax. Read by
`habit-sensors`, the stage that starts the run, and checked before anything else
in the config is interpreted — the reason the key exists is that the rest of the
file may be newer than the reader.

Every case below runs the real pipeline over a stub sensor. Discovery is opt-in
(#97), so the config names a scope.

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
[]
```

📄src/a.txt
```text
a
```

## Today

### A version floor is rejected as an unknown key

Delete this case when the fix lands.

`requires` is not a key the config loader consumes, and #102 rejects what nothing
consumes. So the one thing a project would write to protect itself is the one
thing that stops the run — correctly, by the rule as it stands, and uselessly, by
the reader's intent.

📄.habit-hooks/config.toml
```toml
requires = ">=1.1.0"
plugins  = ["generic"]
files    = ["src/**"]
```

```bash
habit-sensors --all
```

🖥️ ❌ 2

🚨
```text
habit-sensors: unknown config key 'requires' in the project config; known keys: files, plugins, runners, scope, sensors, smells, transformers
```

### A config naming a part this client lacks fails the wrapper too — keep this case

**Keep this case after the fix.** This is the guard that makes a version floor
enforceable, and it is the exact shape 1.0.3 got wrong: the runner refuses a
config it cannot honour, and `habit-hooks` — the binary a git hook runs — must
carry that refusal out, never print ✅ over it.

`snooze-until-merged` stands in for any part a newer config names and this client
does not ship. The runner stops at exit 2 without writing findings; the mapper
sees an empty pipe and coaches it as an incomplete run rather than a clean one.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
files        = ["src/**"]
transformers = ["snooze-until-merged"]
```

```bash
habit-hooks --all
```

🖥️ ❌ 2
```text
── incomplete-run (1 issue) ──

⚠️ Habit Hooks: this run did not complete — a tool broke, so a clean result cannot be trusted.

habit-mapper: nothing arrived on stdin — the sensors stage exited before it wrote any findings
Fix the broken tool (its full diagnosis is on stderr) and re-run; do not treat this change as checked.
```

🚨
```text
habit-sensors: no transformer 'snooze-until-merged' in ['generic'] or the core
```

### A config naming only parts this client has runs clean — keep this case

**Keep this case after the fix.** The discriminator for the case above: the
failure there is about *this client's vocabulary*, not about a malformed config.
Same fixture, naming the transformer this client does ship, and the run is green.

📄.habit-hooks/config.toml
```toml
plugins      = ["generic"]
files        = ["src/**"]
transformers = ["snooze"]
```

```bash
habit-hooks --all
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

## Wanted

`requires` is read first and compared against the installed distribution's own
version — the same number `--version` prints. A run that meets the floor is
unaffected; a run that does not stops before it can produce findings nobody
should trust, naming both versions and the fix. Exit 2, because an installation
too old to honour the config is a failure of the tool, not a statement about the
code (#103).

### A satisfied version floor runs normally 🟡

The installed version meets the floor, so the key changes nothing at all.

📄.habit-hooks/config.toml
```toml
requires = ">=1.0.0"
plugins  = ["generic"]
files    = ["src/**"]
```

```bash
habit-sensors --all | jq -c '.'
```

🖥️ ✅
```json
[]
```

### An unmet version floor stops the run and names both versions 🟡

A floor no installed build can meet. The message says what is installed, what the
project asked for, and how to fix it — a project that pins its floor once should
never have to hand-sync a literal into a workflow file and two lines of prose.

📄.habit-hooks/config.toml
```toml
requires = ">=99.0.0"
plugins  = ["generic"]
files    = ["src/**"]
```

```bash
habit-sensors --all
```

🖥️ ❌ 2

🚨
```text
habit-sensors: this project requires habit-hooks >=99.0.0, but v1.1.0 is installed — upgrade with `pip install -U habit-hooks`
```

### An unmet floor cannot be papered over by the wrapper 🟡

The floor is only worth writing if the binary a hook runs honours it. `habit-hooks`
must fail, and must not print the pass reminder.

📄.habit-hooks/config.toml
```toml
requires = ">=99.0.0"
plugins  = ["generic"]
files    = ["src/**"]
```

```bash
habit-hooks --all 2>&1 | grep -c '✅'
```

🖥️ ❌ 1
```text
0
```
