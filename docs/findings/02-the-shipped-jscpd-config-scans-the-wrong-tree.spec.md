# 02. The shipped jscpd config scans the wrong tree

The generic plugin ships `.jscpd.json` with `path: ["src"]`, and `sensors/jscpd.py`
reads that key and hands it to jscpd as the scan root. Nothing connects it to the
run: not the project's `[files]`, not the paths the run was asked about. jscpd
looks in `src`, only in `src`, whatever the project is.

For a monorepo — sources in `packages/*/src`, nothing at the root called `src` —
that means the duplication rule is not enforced at all. The field study on
OpenBoard measured it as 1880 duplication findings dropping to 0 on adoption.

The reverse costs the same. Ask about one file in `app/` and the sensor still
reports clones out of `src/legacy/`: files `[files]` excluded and the run never
named. The scan set is a constant, so it is wrong in both directions at once.

```text
$ tree -L 2
packages/app/src/csv-export.ts     ← the duplicated pair lives here
packages/app/src/json-export.ts
$ habit-sensors --all
[]                                  ← jscpd looked in ./src and found nothing
```

**This is a residual gap, not a fresh discovery.** Part of it was already fixed
once, and whoever picks this up needs to know which part. CLAUDE.md records the
fix under *"jscpd resolves a config's relative `path` against the config file,
not cwd"*: `jscpd --config <abs path>` resolves the config's own `path: ["src"]`
relative to the **config file's** directory, so a plugin-shipped config scanned
the plugin's package directory and found nothing in the consumer's repo at all.
`sensors/jscpd.py` therefore reads `path` out of the config (`scan_paths`) and
passes those entries as positional arguments, which jscpd resolves against cwd.
That works, and it must not regress — the last case in `Today` is its guard, not
a defect.

What that fix corrected is *where* the path is resolved. Two things it did not
touch:

1. **The value being resolved.** `path: ["src"]` is still the shipped default, so
   correct resolution is applied to a scan root that a monorepo does not have.
   That is this finding.
2. **The spelling jscpd reports back.** `occurrence()` passes `side["name"]`
   through verbatim, so whatever jscpd prints becomes the finding's key and
   `details.file`; the sensor promises nothing about it. The field study on
   3dmaze recorded the scan-root-relative spelling — `reporting/csv-export.ts`
   for `src/reporting/csv-export.ts`, 68 of 68 keys naming files that do not
   exist, and lexical anchoring (#79) cannot catch it because such a path already
   looks project-relative. On this checkout that half does **not** reproduce:
   jscpd 4.2.5, the version pinned here, prints names relative to the working
   directory (verified with the scan root given both relatively and absolutely),
   so the keys anchor correctly. The keeper case below is what currently makes
   that true, and it is true of the tool rather than of the sensor — which is why
   `Wanted` asks for it as a guard rather than leaving it to the next jscpd.

The Node tools live in `plugins/generic/node_modules`; the intro symlinks that
into each case as `./node_modules` and puts its `.bin` on `PATH` once.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**/*.ts"]

[sensors.line-count]
disabled = true
```

📄packages/app/src/csv-export.ts
```typescript
export function toCsv(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient, scaled };
}
```

📄packages/app/src/json-export.ts
```typescript
export function toJson(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient, scaled };
}
```

```bash
ln -s ../../plugins/generic/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## Today

### A project with no root `src/` fails the run with a stack trace about a path nobody configured

Delete this case when the fix lands.

The commonest monorepo shape: everything under `packages/`, no root `src`. jscpd
4.2.5 calls `realpathSync` on each scan root before it starts, so the missing
directory is an `ENOENT` — the sensor dies, the run is incomplete, and the
duplicated pair two directories away is never looked at. The only thing the
project is told is a Node stack trace naming a `src` it does not have and never
asked for.

```bash
habit-sensors --all >out.json 2>err.txt; echo "exit=$?"
jq -c 'map(.smell)' out.json
grep -o "ENOENT: no such file or directory, lstat .*" err.txt | sed "s|lstat .*|lstat <project>/src|" | sort -u
```

🖥️ ✅
```text
exit=1
["incomplete-run"]
ENOENT: no such file or directory, lstat <project>/src
```

### A clone outside the shipped scan root is reported as a clean project

Delete this case when the fix lands.

Give the same project a root `src` holding something unrelated and the crash goes
away — and with it every trace that anything was skipped. jscpd scans `src`,
finds nothing, exits 0. The duplicated pair under `packages/` is not in the scan
set, so it is not in the answer: an empty findings array, exit 0, and not one
line of notice on stderr. This is the shape the OpenBoard study measured.

📄src/version.ts
```typescript
export const version = "1.0.0";
```

```bash
habit-sensors --all >out.json 2>err.txt; echo "exit=$?"
jq -c 'map(.smell)' out.json
grep -c "^habit-sensors: sensor" err.txt || true
```

🖥️ ✅
```text
exit=0
[]
0
```

### A file the project scoped out is reported anyway

Delete this case when the fix lands.

The same constant scan set, seen from the other side. `[files]` names `app/**`,
and the run asks about one file by name — `--file app/main.ts`. jscpd still scans
`src`, so the answer is about `src/legacy/`: two files the project excluded from
its source set, in a run that asked about neither. A scoped run cannot narrow
this sensor, and a project cannot exclude a directory from it.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["app/**/*.ts"]

[sensors.line-count]
disabled = true
```

📄src/legacy/csv-export.ts
```typescript
export function toCsv(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient, scaled };
}
```

📄src/legacy/json-export.ts
```typescript
export function toJson(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient, scaled };
}
```

📄app/main.ts
```typescript
export const main = 1;
```

```bash
habit-sensors --file app/main.ts 2>/dev/null | jq -c '[.[] | {smell, keys: ([.issues[].key] | sort)}]'
```

🖥️ ✅
```text
[{"smell":"duplicated-code","keys":["src/legacy/csv-export.ts","src/legacy/json-export.ts"]}]
```

### A relative `path` in the shipped config is resolved against the project, not against the config file

**Keep this case when the fix lands** — it is the regression guard for the fix
already in place, not a defect. `.jscpd.json` is loaded from inside the installed
package by absolute path, and jscpd would resolve its `path: ["src"]` relative to
*that* directory; there is no `src` there, so the sensor would scan nothing in
every project on earth. `scan_paths` reading the key and passing it positionally
is what makes `src` mean the project's `src`. This case is also what currently
keeps the keys honest: jscpd 4.2.5 spells them relative to the working directory,
so every key names a file the project really has.

📄src/reporting/csv-export.ts
```typescript
export function toCsv(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient, scaled };
}
```

📄src/reporting/json-export.ts
```typescript
export function toJson(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient, scaled };
}
```

```bash
test -d ../../plugins/generic/src/habit_hooks_generic/src || echo "no src/ beside the shipped config"
habit-sensors --all 2>/dev/null | jq -c '[.[] | {smell, keys: ([.issues[].key] | sort)}]'
habit-sensors --all 2>/dev/null | jq -r '.[].issues[].key' | sort | while read -r key; do test -e "$key" && echo "exists $key"; done
```

🖥️ ✅
```text
no src/ beside the shipped config
[{"smell":"duplicated-code","keys":["src/reporting/csv-export.ts","src/reporting/json-export.ts"]}]
exists src/reporting/csv-export.ts
exists src/reporting/json-export.ts
```

## Wanted

The scan set is the project's scope, not a constant. The plugin config keeps
what it is good at — `threshold`, `minLines`, `minTokens`, `ignore` — and stops
deciding *where* the project's code is, which only the project knows.

Where a scan set still resolves to nothing (a scoped run that names no file jscpd
can read), that is said out loud. Silence is the one answer a detector must never
give, because it is the answer a clean project gives.

### The scan set follows the project scope 🟡

The monorepo from the intro, unchanged: no root `src`, the duplicated pair under
`packages/app/src`. The scope names those files, so that is what is scanned, and
the clone is found.

```bash
habit-sensors --all | jq -c '[.[] | {smell, keys: ([.issues[].key] | sort)}]'
```

🖥️ ✅
```text
[{"smell":"duplicated-code","keys":["packages/app/src/csv-export.ts","packages/app/src/json-export.ts"]}]
```

### A scan set that resolves to nothing says so 🟡

A scope that keeps no file the duplication detector can read is a run that
measured nothing, and it is announced the way every other "measured nothing" is
(#93, `scope_notices.py`) — on stderr, naming the sensor, with an empty findings
array rather than a fabricated clean bill.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["docs/**/*.md"]

[sensors.line-count]
disabled = true
```

📄docs/notes.md
```markdown
Just prose.
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
habit-sensors: sensor 'jscpd' examined no files — the scope kept none it can read
```

### Every key a jscpd finding carries names a file the project has 🟡

The guard the sensor does not have. jscpd reports paths relative to its own
working directory today, so anchoring (#79) blesses them and they happen to be
right; a scan root the tool decides to report relative to instead would produce
keys that are already lexically relative, sail through anchoring unchanged, and
give the snooze index keys that can never match a real file. Resolving reported
paths against the scan root before anchoring makes it true by construction.

```bash
habit-sensors --all | jq -r '.[].issues[].key' | while read -r key; do test -e "$key" && echo "exists $key"; done
```

🖥️ ✅
```text
exists packages/app/src/csv-export.ts
exists packages/app/src/json-export.ts
```
