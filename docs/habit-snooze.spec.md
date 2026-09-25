# habit-snooze — ignoring findings you have approved

When using habit-hooks, you may have findings you agree with but do not want to fix right away. habit-snooze lets you set those findings aside so you can work through warnings gradually, while unrelated findings continue to be reported. For snoozes tied to a file, the finding comes back once that file changes, so a snooze does not hide an issue indefinitely after the code has moved on; after reviewing the change, you can snooze it again.

Use `--snooze` to add snoozes, `--prune` to remove ones that no longer apply, and `--list` to see what's currently snoozed. Running `habit-snooze` on its own, with no flags, just applies the existing snoozes to filter findings — it doesn't change what's saved.

## Basic behaviour

`habit-snooze` is a transformer ([architecture.md](architecture.md)) that removes approved issues and passes everything else through.
By default all findings pass through.

⌨️
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
## Snooze current issues

Snoozes are checked into the repository as `.habit-hooks/snooze.json`, so the whole team shares the same list. The default snooze key is the file name (see [sensor-interface.spec.md](sensor-interface.spec.md)), so one snooze can cover every issue reported for that file.

`--snooze` adds all current findings to the snooze list. 

⌨️
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
```bash
habit-snooze --snooze && habit-snooze --list
```
🖥️ ✅
```text
src/x.ts
```

## Issues resurface on next edit

When you snooze an issue, habit-snooze will keep filtering it out as long as the file's contents remains the same; 

>> "An edit brings the issue back" should belong here. and it should set up the re snoose case bellow

When the file is edited next time, the issue comes back. We recommend fixing the issue at that time, however running `--snooze` again approves the new version.

When you snooze an issue tied to a file, habit-snooze remembers what that file looked like when you approved it. The issue stays snoozed as long as the file still matches; edit the file and the issue comes back so you can review the change. Run `--snooze` again to approve the new version.

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
    "details": {
      "maxAllowed": 200
    },
    "issues": [
      {
        "key": "src/x.ts",
        "details": {
          "file": "src/x.ts",
          "lines": 251
        }
      }
    ]
  }
]
```
```bash
habit-snooze --snooze
```

## Remove snoozes for findings that no longer exist

Use `habit-sensors --all --no-snooze | habit-snooze --prune` when you want to remove snoozes for issues that are no longer reported. The command keeps snoozes for issues that are still present.

```bash
habit-sensors --all --no-snooze | habit-snooze --prune && habit-snooze --list
```
🖥️ ✅
```text
src/x.ts
```
