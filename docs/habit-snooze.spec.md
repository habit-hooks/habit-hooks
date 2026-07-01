# habit-snooze — the snooze transformer

Snoozing is a **transformer** ([architecture.md](architecture.md)): a
`findings → findings` step that drops the issues a project has chosen to ignore
and passes everything else through. It sits at the outermost level of the run,
where it sees every finding.

What it drops is decided by a small, checked-in **index** of snoozed keys. An
issue is snoozed when its `key` is in the index. Because `key` defaults to the
filename ([sensor-interface.spec.md](sensor-interface.spec.md)), snoozing a key
snoozes a whole file's issues at once — and a sensor that wants finer control
just chooses a finer `key`.

Two rules cover the whole transform:

- **Drop snoozed issues, keep the rest.** Within a finding, each issue whose
  `key` is in the index is removed; the others stay.
- **A finding with no issues left is dropped.** When the last issue goes, the
  finding goes with it.

The `--snooze` / `--prune` / `--list` commands maintain the index. They are the
only things that write it; the transform itself only reads it.

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

## `--prune` drops keys that didn't appear in the latest run

A snoozed key whose issue no longer shows up — the smell was fixed, or the file
deleted — is stale. `--prune` reads the latest findings and keeps only the index
keys that appear in them, so a fixed snooze doesn't linger forever. Here two keys
are snoozed but only `src/x.ts` recurs, so `src/y.ts` is pruned away.

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
habit-snooze --prune && habit-snooze --list
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
