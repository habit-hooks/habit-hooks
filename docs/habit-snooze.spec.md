# habit-snooze — ignoring findings you have approved

When using habit-hooks, you may have findings you agree with but do not want to fix right away. habit-snooze lets you set those findings aside so you can work through warnings gradually, while unrelated findings continue to be reported. For snoozes tied to a file, the finding comes back once that file changes, so a snooze does not hide an issue indefinitely after the code has moved on; after reviewing the change, you can snooze it again.

`habit-snooze` is a transformer ([architecture.md](architecture.md)) that removes approved issues and passes everything else through.

Snoozes are saved in `.habit-hooks/snooze.json`, which is checked into your repo so the whole team shares the same list. Each snooze is identified by a key — by default the finding's filename ([sensor-interface.spec.md](sensor-interface.spec.md)) — so one snooze can cover every issue reported for that file.

Use `--snooze` to add snoozes, `--prune` to remove ones that no longer apply, and `--list` to see what's currently snoozed. Running `habit-snooze` on its own, with no flags, just applies the existing snoozes to filter findings — it doesn't change what's saved.

When you snooze an issue that's tied to a file, habit-snooze remembers what that file looked like at the time. The issue stays snoozed as long as the file's contents still match what was approved (differences in line endings alone don't count as a change); edit the file and the issue comes back so you can review it. Running `--snooze` again approves the new version. (`snooze-until-changed` is a deprecated alias for `snooze`.)

## By default, findings pass through

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

## Snooze remaining issues

`--snooze` reads the findings you give it and adds each issue to your list of approved snoozes. If the finding points at a file, that file's current contents become the approved version to watch; if it doesn't, the issue is simply tracked by its key.

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

When a finding contains multiple issues, snoozing one issue removes only that issue from the results, and when snoozing removes the last issue from a finding, the finding is removed entirely. Other unsnoozed issues in the same finding continue to be reported.

## Remove snoozes for findings that no longer exist

When a snoozed issue stops being reported — the smell was fixed, or the file is gone — its snooze is stale. Use `habit-sensors --all --no-snooze | habit-snooze --prune` to remove stale snoozes and keep the rest. The `--no-snooze` matters: `--prune` can only judge a snooze against an issue it can still see, and the default output has already hidden the snoozed ones. The examples here drive that pipeline through a stub sensor that reports its findings from a file:

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

### It keeps snoozes that still apply and drops the rest

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

If a scan comes back with no findings at all — for example because something upstream is misconfigured or broken — `--prune` will not wipe out your existing snoozes. It's safer to assume the scan failed than to assume every snooze is stale.

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

## `--list` shows what's currently snoozed

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

## Editing an approved file brings its issues back

When you snooze an issue tied to a file, habit-snooze remembers what that file looked like when you approved it. The issue stays snoozed as long as the file still matches; edit the file and the issue comes back so you can review the change. Run `--snooze` again to approve the new version.

Every case below starts from the same state: two files, with `src/x.ts` approved through the real command.

📄src/x.ts
```ts
export const equal = (a, b) => a == b;
```

📄src/other.ts
```ts
export const untouched = 1;
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
habit-snooze --snooze
```

### An approved file stays snoozed

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

### An edit brings the issue back

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
habit-snooze | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/x.ts"]
```

### `--snooze` approves what is there now

After reviewing the changed file, run `--snooze` again to approve its current state.

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
habit-snooze | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/x.ts"]
```

```bash
habit-snooze --snooze && habit-snooze | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
[]
```

```bash
printf 'export const more = 2;\n' >> src/x.ts
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
["src/x.ts"]
```
