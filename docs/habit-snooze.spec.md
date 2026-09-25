# habit-snooze — ignoring findings you have approved

When using habit-hooks, you may have findings you agree with but do not want to fix right away. habit-snooze lets you set those findings aside so you can work through warnings gradually, while unrelated findings continue to be reported. For snoozes tied to a file, the finding comes back once that file changes, so a snooze does not hide an issue indefinitely after the code has moved on; after reviewing the change, you can snooze it again.

Use `--snooze` to add snoozes, `--prune` to remove ones that no longer apply, and `--list` to see what's currently snoozed. Running `habit-snooze` on its own, with no flags, just applies the existing snoozes to filter findings — it doesn't change what's saved.

The examples below share one small project and run it through the real pipeline; the sensor is the python plugin's comment sensor, so every finding is one a real run would report:

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.ruff]
disabled = true

[sensors.deptry]
disabled = true
```

📄src/x.py
```python
total = 1 + 2
# total is 3
```

📄src/other.py
```python
ready = True
```

## Basic behaviour

`habit-snooze` is a transformer ([architecture.md](architecture.md)) that removes approved issues and passes everything else through.
By default all findings pass through.

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "non-essential-comment",
    "details": {},
    "issues": [
      {
        "key": "src/x.py",
        "details": {
          "file": "src/x.py",
          "line": 2,
          "message": "# total is 3",
          "source": "comment"
        }
      }
    ],
    "language": "python"
  }
]
```

## Snooze current issues 

Snoozes are checked into the repository as `.habit-hooks/snooze.json`, so the whole team shares the same list. The default snooze key is the file name (see [sensor-interface.spec.md](sensor-interface.spec.md)), so one snooze can cover every issue reported for that file.

`--snooze` adds all current findings to the snooze list.

(example continued from previous section)

```bash
habit-sensors --all | habit-snooze --snooze && habit-snooze --list
```
🖥️ ✅
```text
src/x.py
```

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[]
```

## Issues resurface on next edit

When you snooze an issue, habit-snooze will keep filtering it out as long as the file's contents remains the same.

(example continued from previous section)

```bash
printf '# what other.py is for\n' >> src/other.py
```

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "non-essential-comment",
    "details": {},
    "issues": [
      {
        "key": "src/other.py",
        "details": {
          "file": "src/other.py",
          "line": 2,
          "message": "# what other.py is for",
          "source": "comment"
        }
      }
    ],
    "language": "python"
  }
]
```

When the file is edited next time, the issue comes back. We recommend fixing the issue at that time, however running `--snooze` again approves the new version.

```bash
printf '# another comment\n' >> src/x.py
```

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "non-essential-comment",
    "details": {},
    "issues": [
      {
        "key": "src/other.py",
        "details": {
          "file": "src/other.py",
          "line": 2,
          "message": "# what other.py is for",
          "source": "comment"
        }
      },
      {
        "key": "src/x.py",
        "details": {
          "file": "src/x.py",
          "line": 2,
          "message": "# total is 3",
          "source": "comment"
        }
      },
      {
        "key": "src/x.py",
        "details": {
          "file": "src/x.py",
          "line": 3,
          "message": "# another comment",
          "source": "comment"
        }
      }
    ],
    "language": "python"
  }
]
```

```bash
habit-sensors --all | habit-snooze --snooze && habit-sensors --all | jq .
```
🖥️ ✅
```json
[]
```

## Remove snoozes for findings that no longer exist

Use `habit-sensors --all --no-snooze | habit-snooze --prune` when you want to remove snoozes for issues that are no longer reported. The command keeps snoozes for issues that are still present.

Both issues in `src/x.py` get fixed:

(example continued from previous section)

📄src/x.py
```python
total = 1 + 2
```

```bash
habit-sensors --all --no-snooze | habit-snooze --prune && habit-snooze --list
```
🖥️ ✅
```text
src/other.py
```
