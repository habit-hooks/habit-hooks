# Snoozer

Snoozing is a **filter sensor** ([sensors.md](sensors.md)): it reads the
`{smell, details}` JSON array and drops the findings a project has snoozed. A
snooze lapses when the file changes. The `--snooze` / `--prune` / `--list` commands
maintain the checked-in index.

```bash
habit-snooze() { ../../habit-snooze; }
```

## Filtering

### An unsnoozed finding passes through 🟡

With an empty index, every finding survives.

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```text
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```

### A snoozed finding is dropped 🟡

`--snooze` records the finding against its file; the filter then drops it.

📄src/x.ts
```ts
export const x = 1;
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```

```bash
habit-snooze --snooze --all
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```text
[]
```

### A snooze lapses when the file changes 🟡

Editing the file makes the snoozed finding resurface.

📄src/x.ts
```ts
export const x = 1;
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```

```bash
habit-snooze --snooze --all
```

📄src/x.ts
```ts
export const x = 2;
```

⌨️
```json
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```

```bash
habit-snooze | jq .
```

🖥️ ✅
```text
[
  {
    "smell": "loose-equality",
    "details": {
      "file": "src/x.ts",
      "line": 1
    }
  }
]
```
