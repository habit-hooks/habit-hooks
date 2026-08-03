# habit-snooze — the snooze transformer

Snoozing is a **transformer** ([architecture.md](architecture.md)): a
`findings → findings` step that drops the issues a project has chosen to ignore
and passes everything else through. It sits at the outermost level of the run,
where it sees every finding.

What it drops is decided by a small, checked-in **index** of snoozed keys. An
issue is snoozed when its `key` is in the index. Because `key` defaults to the
filename ([sensor-interface.spec.md](sensor-interface.spec.md)), snoozing a key
snoozes a whole file's issues at once — and a sensor that wants finer control
just chooses a finer `key`. A key that is a filename is one the runner has
already anchored to the project, so an index recorded here matches on a
teammate's checkout and in CI.

Two rules cover the whole transform:

- **Drop snoozed issues, keep the rest.** Within a finding, each issue whose
  `key` is in the index is removed; the others stay.
- **A finding with no issues left is dropped.** When the last issue goes, the
  finding goes with it.

The `--snooze` / `--prune` / `--list` commands maintain the index. They are the
only things that write it; the transform itself only reads it.

A snooze recorded this way lasts until someone removes it from the index. A
project that wants the index to be a **ratchet** instead — an exemption that
lapses the moment the file is touched — runs the same command with
`--until-changed`, shipped as the separate `snooze-until-changed` transformer
and described [below](#--until-changed-keeps-a-snooze-only-while-its-file-is-unchanged).

## An unsnoozed issue passes through

With an empty index, every finding survives untouched.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "maxAllowed": 0
    },
    "issues": [
      {
        "key": "src/x.ts",
        "details": {
          "file": "src/x.ts",
          "line": 1
        }
      }
    ]
  }
]
```

## `--snooze` records an issue's key into the index

`--snooze` reads the findings on stdin and adds each issue's `key` to the index.
`--list` then shows what is snoozed.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  }
]
```

```bash
habit-snooze --snooze && habit-snooze --list
```

🖥️ ✅
```text
src/x.ts
```

## A snoozed issue is dropped from its finding

A finding with two issues loses the snoozed one and keeps the other.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  }
]
```

```bash
habit-snooze --snooze
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } },
      { "key": "src/y.ts", "details": { "file": "src/y.ts", "line": 9 } }
    ]
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "maxAllowed": 0
    },
    "issues": [
      {
        "key": "src/y.ts",
        "details": {
          "file": "src/y.ts",
          "line": 9
        }
      }
    ]
  }
]
```

## A finding loses its only issue and disappears

When the snoozed key was the finding's last issue, the whole finding is dropped —
the output is an empty array, not a finding with an empty `issues` list.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  }
]
```

```bash
habit-snooze --snooze
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```json
[]
```

## A snooze holds even after its file changes

The default snooze is **unconditional**: it never asks git anything, so the
exemption survives any amount of new debt in the file and lasts until someone
takes the key out of the index. That is deliberate — a project upgrading must
not find its snoozes re-arming by themselves — and it is the whole difference
from [`--until-changed`](#--until-changed-keeps-a-snooze-only-while-its-file-is-unchanged)
below. The file here is committed and then edited, and the issue stays dropped.

📄src/x.ts
```ts
export const equal = (a, b) => a == b;
```

📄.habit-hooks/snooze.json
```json
["src/x.ts"]
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add src/x.ts &&
  git commit -q -m baseline &&
  printf 'export const extra = 1;\n' >> src/x.ts
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

## An empty index changes nothing

Snooze runs by default ([habit-sensors.spec.md](habit-sensors.spec.md)), so a
project that has never snoozed anything must get its findings back byte for
byte. Dropping happens only where a key matched: a finding that arrives with no
issues has nothing snoozed in it and passes through, unlike one whose last issue
*was* snoozed above.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  },
  {
    "smell": "duplicated-code",
    "details": {},
    "issues": []
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "maxAllowed": 0
    },
    "issues": [
      {
        "key": "src/x.ts",
        "details": {
          "file": "src/x.ts",
          "line": 1
        }
      }
    ]
  },
  {
    "smell": "duplicated-code",
    "details": {},
    "issues": []
  }
]
```

## `--prune` reads a snooze-free view of the run

A snoozed key whose issue no longer shows up — the smell was fixed, or the file
deleted — is stale, and `--prune` drops it. But `--prune` must read the findings
**before** the snooze transformer filtered them: the default pipe has already
stripped every snoozed issue, so a naive `--prune` would see none of them and
empty the whole index (#94). The documented pipeline therefore runs
`habit-sensors --no-snooze`, so `--prune` compares the index against everything
the run still finds — snoozed or not.

These cases drive that real pipeline through a stub sensor rather than hand-fed
findings, so the bypass that hid the bug cannot come back. Discovery is opt-in
(#97), so the config names a scope; `["**"]` is every file the case writes.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "cat ${dir}/alpha.json"
```

### It keeps a still-violating key and drops one that no longer appears

Two keys are snoozed, but the run only still reports `src/x.ts` (the `src/y.ts`
smell was fixed). Pruning keeps `src/x.ts` and reaps `src/y.ts`.

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"loose-equality","details":{"maxAllowed":0},"issues":[{"key":"src/x.ts","details":{"file":"src/x.ts","line":1}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/x.ts", "src/y.ts"]
```

```bash
habit-sensors --all --no-snooze | habit-snooze --prune && habit-snooze --list
```

🖥️ ✅
```text
src/x.ts
```

### It refuses to empty a populated index when the run measured nothing

An empty run means "nothing was measured", not "every exemption is obsolete", so
`--prune` refuses to touch a populated index and says why (the false-clean class
of #78/#84). Here the sensor reports nothing, yet the snooze survives.

📄.habit-hooks/generic/sensors/alpha.json
```json
[]
```

📄.habit-hooks/snooze.json
```json
["src/x.ts"]
```

```bash
habit-sensors --all --no-snooze | habit-snooze --prune
```

🖥️ ❌ 1

```bash
habit-snooze --list
```

🖥️ ✅
```text
src/x.ts
```

## `--list` shows the index

`--list` prints the snoozed keys, one per line, so the checked-in index is
reviewable without reading the file by hand.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } },
      { "key": "src/y.ts", "details": { "file": "src/y.ts", "line": 9 } }
    ]
  }
]
```

```bash
habit-snooze --snooze && habit-snooze --list
```

🖥️ ✅
```text
src/x.ts
src/y.ts
```

## A corrupt index fails the tool, not the code

The index is a checked-in file people edit by hand, so a broken one is a failure
of the tool itself — not a finding about the code. It exits **2**, the code
[habit-sensors.spec.md](habit-sensors.spec.md) already uses for a rejected config
or an unresolvable base ref, and names the file and what it expected on stderr.
The `--prune` refusal above is the other kind — a judgement about the run — and
keeps exit 1.

📄.habit-hooks/snooze.json
```json
{"src/x.ts": "why"}
```

```bash
habit-snooze --list 2>&1 >/dev/null | sed 's| /.*/\.habit-hooks/| .habit-hooks/|'
```

🖥️ ❌ 2
```text
habit-snooze: .habit-hooks/snooze.json: expected a JSON list of string keys, got an object
```

## `--until-changed` keeps a snooze only while its file is unchanged

`habit-snooze --until-changed` reads the same index, but a snoozed issue is
dropped only while the file it sits in is unchanged. Change that file — a commit
since the base ref, or an edit still in the working tree — and its issues come
back. That is what turns the index into a ratchet: debt stays exempt until you
are editing the file anyway, which is exactly when you can clear it.

It ships as a second transformer, `snooze-until-changed`, next to the
unconditional `snooze`. Snoozing does not change under anyone's feet: a project
opts in by naming it ([config.md](config.md)).

```toml
transformers = ["snooze-until-changed"]
```

An issue is anchored to the file in its `details.file`, falling back to its
`key`. "Changed" is measured from where this branch left the base — the merge
base of `[scope] branchBase` and `HEAD` — so work someone else lands on the base
ref afterwards never lapses a snooze you did not touch.

Two kinds of git silence are kept apart. A path git cannot place — untracked, or
no repository at all — reads as *unchanged*, so the snooze holds. A base ref a
real repository cannot resolve is a **failure**: it would otherwise make every
snooze permanent again, silently, which is the bug this transformer exists to
fix.

Every case below inherits this repository: `src/x.ts` and `src/other.ts`
committed on `main`, with `src/x.ts` snoozed.

📄src/x.ts
```ts
export const equal = (a, b) => a == b;
```

📄src/other.ts
```ts
export const untouched = 1;
```

📄.habit-hooks/snooze.json
```json
["src/x.ts"]
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add src &&
  git commit -q -m baseline
```

### An unchanged file stays snoozed

The file is byte for byte what it is at the base ref, so the snooze still
applies and its only issue is dropped — the same outcome plain `snooze` gives.

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

### An edit in the working tree lapses the snooze

Nothing is committed here: the file differs from the base ref only by an
uncommitted edit, and that alone re-surfaces the issue.

```bash
printf 'export const extra = 1;\n' >> src/x.ts
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/x.ts"]
```

### A commit against the base ref lapses the snooze

The change is committed on a branch, so the working tree is clean — the
`git diff --quiet` in the setup fails the case if it is not. The only difference
left is against `main`, and it is enough.

```bash
git checkout -q -b feature &&
  printf 'export const extra = 1;\n' >> src/x.ts &&
  git commit -q -am grow &&
  git diff --quiet
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/x.ts"]
```

### The base ref is the configured `[scope] branchBase`

A project whose trunk is not called `main` says so in `[scope] branchBase`, and
the comparison follows it. Here the base branch is renamed to `trunk`, so a run
that assumed `main` would find no such ref — and, degrading safely, would keep
the snooze instead of lapsing it.

📄.habit-hooks/config.toml
```toml
[scope]
branchBase = "trunk"
```

```bash
git branch -m main trunk &&
  printf 'export const extra = 1;\n' >> src/x.ts
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/x.ts"]
```

### `--config` selects the base ref the transformer lapses against

A run invoked with `--config <path>` scopes the sensors stage from that file, so
the snooze transformer must read `[scope] branchBase` from the *same* file — or
the run lapses exemptions against a different base than it scanned, and answers
one question two ways. Here the default `.habit-hooks/config.toml` names a base
ref this checkout does not have, which on its own would fail the run; `ci.toml` —
the file the run was handed — names `main`. Reading the base from `ci.toml`,
`main` resolves, `src/x.ts` is unchanged against it, and the snooze holds.

📄.habit-hooks/config.toml
```toml
[scope]
branchBase = "phantom-base"
```

📄ci.toml
```toml
[scope]
branchBase = "main"
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed --config ci.toml | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

### The snooze is anchored to `details.file`, not to the key

A sensor keys an issue by whatever groups it best — `deptry` by module name,
`knip` by export name ([sensor-interface.spec.md](sensor-interface.spec.md)) —
so the file to compare comes from `details.file`. The key below is a module
name, not a path git could ever have heard of, and the snooze still lapses when
`src/x.ts` changes.

📄.habit-hooks/snooze.json
```json
["requests"]
```

```bash
printf 'export const extra = 1;\n' >> src/x.ts
```

⌨️
```json
[
  {
    "smell": "unused-dependency",
    "details": {},
    "issues": [
      { "key": "requests", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["requests"]
```

### A file git never tracked keeps its snooze

An untracked file has no base-ref state to compare against, so git reports no
difference and the snooze holds. Re-arming here would mean acting on an answer
git never gave.

📄src/new.ts
```ts
export const other = 1;
```

📄.habit-hooks/snooze.json
```json
["src/new.ts"]
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/new.ts", "details": { "file": "src/new.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

### Work landed on the base ref afterwards lapses nothing

The comparison starts at the merge base, not at the tip of the base ref, so a
branch is only ever measured against the debt it touched itself. Here the branch
edits `src/x.ts` while somebody else lands a change to `src/other.ts` on `main`:
one snooze lapses, the other must not — otherwise the gate would fail on debt
this branch never went near.

📄.habit-hooks/snooze.json
```json
["src/x.ts", "src/other.ts"]
```

```bash
git checkout -q -b feature &&
  printf 'export const extra = 1;\n' >> src/x.ts &&
  git commit -q -am "this branch touches x" &&
  git checkout -q main &&
  printf 'export const moved = 2;\n' >> src/other.ts &&
  git commit -q -am "main moves on without us" &&
  git checkout -q feature
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } },
      { "key": "src/other.ts", "details": { "file": "src/other.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/x.ts"]
```

### A base ref this checkout cannot resolve fails the run

A CI checkout that fetched only the pull-request ref has no local `main`, and a
project whose trunk is `master` never had one. Comparing against a ref that is
not there would answer "nothing changed" for every file — every snooze
permanent, no signal, a green run over debt that grew. So it fails instead,
naming the ref and the setting that fixes it. The base branch is renamed here
while `[scope] branchBase` stays at its `main` default.

```bash
git branch -m main trunk &&
  printf 'export const extra = 1;\n' >> src/x.ts
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed
```

🖥️ ❌ 2

🚨
```text
habit-snooze: base ref 'main' does not resolve in this checkout — set [scope] branchBase to a ref it has
```

## `--until-changed` with an empty index changes nothing

With nothing snoozed there is nothing to compare, so the findings come back as
they arrived — including a finding that arrives with no issues at all, which is
passed through rather than dropped.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 } }
    ]
  },
  {
    "smell": "duplicated-code",
    "details": {},
    "issues": []
  }
]
```

```bash
habit-snooze --until-changed | jq .
```

🖥️ ✅
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "maxAllowed": 0
    },
    "issues": [
      {
        "key": "src/x.ts",
        "details": {
          "file": "src/x.ts",
          "line": 1
        }
      }
    ]
  },
  {
    "smell": "duplicated-code",
    "details": {},
    "issues": []
  }
]
```

## A project outside a git repository keeps its snoozes

Without git there is no way to tell whether a file changed, so every snooze
holds — a project that never adopted git still gets the plain snooze behaviour,
and a broken git can never re-arm a whole index at once. Note the difference
from an unresolvable base ref above: there a *real* repository says the
configured ref is missing, which is a mistake worth failing over; here git says
nothing at all.

`GIT_CEILING_DIRECTORIES` is what makes this case honest: the spec harness runs
each case in a directory *inside* this repository's own checkout, so git would
otherwise walk up and answer about habit-hooks itself. A real project outside a
repository needs no such thing.

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

With the ceiling in place git refuses to place this directory at all, which is
the situation under test:

```bash
git rev-parse --is-inside-work-tree
```

🖥️ ❌ 128

📄src/x.ts
```ts
export const equal = (a, b) => a == b;
```

📄.habit-hooks/snooze.json
```json
["src/x.ts"]
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  }
]
```

```bash
habit-snooze --until-changed | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```
