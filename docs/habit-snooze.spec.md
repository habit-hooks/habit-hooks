# habit-snooze — ignoring findings you have approved

When using habit-hooks, you may have findings you agree with but do not want to fix right away. habit-snooze lets you set those findings aside so you can work through warnings gradually, while unrelated findings continue to be reported. For snoozes tied to a file, the finding comes back once that file changes, so a snooze does not hide an issue indefinitely after the code has moved on; after reviewing the change, you can snooze it again.

Use `--snooze` to add snoozes, `--prune` to remove ones that no longer apply, and `--list` to see what's currently snoozed. Running `habit-snooze` on its own, with no flags, just applies the existing snoozes to filter findings — it doesn't change what's saved.

The examples below share one small project and run it through the real pipeline; the sensor is a stub that reports whatever a file says, so the findings stay simple while the snoozing stays real:

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

📄src/x.ts
```ts
export const equal = (a, b) => a == b;
```

📄src/other.ts
```ts
export const untouched = 1;
```

📄.habit-hooks/generic/sensors/alpha.json
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 } }
    ]
  },
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/other.ts", "details": { "file": "src/other.ts", "lines": 300 } }
    ]
  }
]
```

## Basic behaviour

`habit-snooze` is a transformer ([architecture.md](architecture.md)) that removes approved issues and passes everything else through.
By default all findings pass through.

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
["src/x.ts","src/other.ts"]
```

## Snooze current issues (continued)

Snoozes are checked into the repository as `.habit-hooks/snooze.json`, so the whole team shares the same list. The default snooze key is the file name (see [sensor-interface.spec.md](sensor-interface.spec.md)), so one snooze can cover every issue reported for that file.

`--snooze` adds all current findings to the snooze list.

```bash
habit-sensors --all | habit-snooze --snooze && habit-snooze --list
```
🖥️ ✅
```text
src/other.ts
src/x.ts
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
[]
```

## Issues resurface on next edit (continued)

When you snooze an issue, habit-snooze will keep filtering it out as long as the file's contents remains the same.

```bash
printf 'export const touched = 2;\n' >> src/other.ts
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
["src/other.ts"]
```

When the file is edited next time, the issue comes back. We recommend fixing the issue at that time, however running `--snooze` again approves the new version.

```bash
printf 'export const extra = (a, b) => a == b;\n' >> src/x.ts
```

The sensor now also reports the issue the edit created:

📄.habit-hooks/generic/sensors/alpha.json
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 252 } }
    ]
  },
  {
    "smell": "loose-equality",
    "details": { "maxAllowed": 0 },
    "issues": [
      { "key": "src/x.ts", "details": { "file": "src/x.ts", "line": 2 } }
    ]
  },
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/other.ts", "details": { "file": "src/other.ts", "lines": 301 } }
    ]
  }
]
```

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
["src/x.ts","src/x.ts","src/other.ts"]
```

```bash
habit-sensors --all | habit-snooze --snooze && habit-sensors --all | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
[]
```

## Remove snoozes for findings that no longer exist (continued)

Use `habit-sensors --all --no-snooze | habit-snooze --prune` when you want to remove snoozes for issues that are no longer reported. The command keeps snoozes for issues that are still present.

Both issues in `src/x.ts` get fixed:

📄src/x.ts
```ts
export const equal = (a, b) => a === b;
```

📄.habit-hooks/generic/sensors/alpha.json
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/other.ts", "details": { "file": "src/other.ts", "lines": 301 } }
    ]
  }
]
```

```bash
habit-sensors --all --no-snooze | habit-snooze --prune && habit-snooze --list
```
🖥️ ✅
```text
src/other.ts
```
