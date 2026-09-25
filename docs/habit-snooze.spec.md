# habit-snooze — ignoring findings you have approved

`habit-snooze` is a transformer ([architecture.md](architecture.md)) that removes approved issues and passes everything else through.

The checked-in index (`.habit-hooks/snooze.json`) identifies snooze entries by key. File-backed entries also depend on the approved file content; changing that file reactivates the issue. Because `key` defaults to the filename ([sensor-interface.spec.md](sensor-interface.spec.md)), one key can cover all of that file's issues.

`--snooze` updates the index, `--prune` removes stale entries, and `--list` only displays it. The normal transformer only reads the index.

`--snooze` records the approved content of each anchored file. An issue stays snoozed while its normalized content hash (converting CRLF to LF) matches; editing the file reactivates the issue. Running `--snooze` again approves the current state. The `snooze-until-changed` transformer is a deprecated alias of `snooze`.

## An unsnoozed issue passes through

⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}]}]
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

`--snooze` reads findings on stdin and adds each issue's key to the index. When `details.file` is a usable non-empty string, it is used as the file anchor to record approved normalized file content; otherwise the key is used.

⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}]}]
```
```bash
habit-snooze --snooze && habit-snooze --list
```
🖥️ ✅
```text
src/x.ts
```

## A snoozed issue is dropped from its finding

⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}]}]
```
```bash
habit-snooze --snooze
```
⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}, {"key": "src/y.ts", "details": { "file": "src/y.ts", "line": 9 }}]}]
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

If snoozing removes the last issue from a finding, the finding is removed.

⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}]}]
```
```bash
habit-snooze --snooze
```
⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}]}]
```
```bash
habit-snooze | jq .
```
🖥️ ✅
```json
[]
```

## An entry that records nothing keeps holding

An entry written as a bare key has no file content to compare, so it keeps holding regardless of file edits until updated by `--snooze`.

📄src/x.ts
```ts
export const equal = (a, b) => a == b;
```
📄.habit-hooks/snooze.json
```json
["src/x.ts"]
```
```bash
printf 'export const extra = 1;\n' >> src/x.ts
```
⌨️
```json
[{"smell": "oversized-file", "details": { "maxAllowed": 200 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 }}]}]
```
```bash
habit-snooze | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
[]
```

## An empty index changes nothing

A finding that arrives with no issues passes through untouched.

⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}]}, {"smell": "duplicated-code", "details": {}, "issues": []}]
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

`--prune` drops entries whose issues no longer appear. Running `habit-sensors --no-snooze` allows `--prune` to see all findings before snoozing filters them.

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

⌨️
```json
[{"smell": "loose-equality", "details": { "maxAllowed": 0 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "line": 1 }}, {"key": "src/y.ts", "details": { "file": "src/y.ts", "line": 9 }}]}]
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

📄.habit-hooks/snooze.json
```json
{"src/x.ts": "why"}
```
```bash
habit-snooze --list 2>&1 >/dev/null | sed 's| /.*/\.habit-hooks/| .habit-hooks/|'
```
🖥️ ❌ 2
```text
habit-snooze: .habit-hooks/snooze.json: expected a JSON list of snoozed entries, got an object
```

## An edited file brings its issues back until it is approved again

A snooze records approved file content: the issue stays snoozed while the normalized content hash matches, and reactivates when the file is edited. Running `--snooze` approves the current file content.

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
[{"smell": "oversized-file", "details": { "maxAllowed": 200 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 }}]}]
```
```bash
habit-snooze --snooze
```

### An approved file stays snoozed

⌨️
```json
[{"smell": "oversized-file", "details": { "maxAllowed": 200 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 }}]}]
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
[{"smell": "oversized-file", "details": { "maxAllowed": 200 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 }}]}]
```
```bash
habit-snooze | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
["src/x.ts"]
```

### `--snooze` approves what is there now

```bash
printf 'export const extra = 1;\n' >> src/x.ts
```
⌨️
```json
[{"smell": "oversized-file", "details": { "maxAllowed": 200 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 }}]}]
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
[{"smell": "oversized-file", "details": { "maxAllowed": 200 }, "issues": [{"key": "src/x.ts", "details": { "file": "src/x.ts", "lines": 251 }}]}]
```
```bash
habit-snooze | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
["src/x.ts"]
```

### The file anchor can differ from the issue key

The key identifies the snooze entry, but `details.file` (when a usable non-empty string) supplies the file anchor.

⌨️
```json
[{"smell": "unused-dependency", "details": {}, "issues": [{"key": "requests", "details": { "file": "src/x.ts", "line": 1 }}]}]
```
```bash
habit-snooze --snooze
```
```bash
printf 'export const stale = 3;\n' >> src/x.ts
```
⌨️
```json
[{"smell": "unused-dependency", "details": {}, "issues": [{"key": "requests", "details": { "file": "src/x.ts", "line": 1 }}]}]
```
```bash
habit-snooze | jq -c '[.[].issues[].key]'
```
🖥️ ✅
```json
["requests"]
```

### An issue with no usable file anchor stores a bare key

Without a usable file anchor, the entry is written as a bare key into the index.

⌨️
```json
[{"smell": "unused-dependency", "details": {}, "issues": [{"key": "SomeExport", "details": {}}]}]
```
```bash
habit-snooze --snooze && jq -c 'map(if type == "object" then {key: .key, anchors: (.anchors | keys)} else . end)' .habit-hooks/snooze.json
```
🖥️ ✅
```json
["SomeExport",{"key":"src/x.ts","anchors":["src/x.ts"]}]
```
