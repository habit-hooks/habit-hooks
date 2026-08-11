# The generic plugin — acceptance

The generic plugin runs language-agnostic sensors through the real `habit-sensors`
pipeline. These cases run the **actual** tools against a fixture with a known
smell and assert the canonical finding comes out.

The Node tools live in `plugins/generic/node_modules`; the intro symlinks that
into each case as `./node_modules` and puts its `.bin` on `PATH` once.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

```bash
ln -s ../../plugins/generic/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## line-count emits oversized-file over the threshold

The `line-count` sensor flags a file longer than its `--max` threshold (default
200, shipped as replace-on-override `args` in `sensors/line-count.toml`) as
`oversized-file`.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**/*.py"]

[sensors.jscpd]
disabled = true
```

```bash
seq 1 205 | sed 's/^/x/;s/$/ = 0/' > big.py
habit-sensors --all | jq '.[] | {smell, max: .details.maxAllowed, key: .issues[0].key, lines: .issues[0].details.lines}'
```

🖥️ ✅
```json
{
  "smell": "oversized-file",
  "max": 200,
  "key": "big.py",
  "lines": 205
}
```

## line-count threshold is replace-on-override

A project `[sensors.line-count] args` replaces the shipped `--max 200` cleanly, so
a 205-line file no longer fires once the threshold is raised.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files = ["**/*.py"]

[sensors.jscpd]
disabled = true

[sensors.line-count]
args = ["--max", "300"]
```

```bash
seq 1 205 | sed 's/^/x/;s/$/ = 0/' > big.py
habit-sensors --all | jq .
```

🖥️ ✅
```json
[]
```

## jscpd emits duplicated-code for a cloned block

The `jscpd` sensor wraps the real jscpd CLI and shapes each clone into a
`duplicated-code` finding listing both occurrences in `issues`. This project has
no jscpd config of its own — a `package.json` without a `jscpd` key is not one —
so the plugin's shipped `.jscpd.json` (`path: ["src"]`, `minLines: 5`,
`minTokens: 50`, `threshold: 0`) applies, and jscpd scans `src` and reports the
duplicated block.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]

[sensors.line-count]
disabled = true
```

📄package.json
```json
{
  "name": "example",
  "private": true
}
```

📄src/a.ts
```typescript
export function alpha(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient };
}
```

📄src/b.ts
```typescript
export function beta(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient };
}
```

```bash
habit-sensors --all | jq '.[] | {smell, files: [.issues[].key | sub(".*/"; "")], source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "duplicated-code",
  "files": [
    "a.ts",
    "b.ts"
  ],
  "source": "jscpd:duplication"
}
```

## A project's own jscpd config wins over the shipped one

The shipped `.jscpd.json` answers "this project has none"; it never overrides a
project that has thought about its own. habit-hooks looks exactly where jscpd
looks — a `.jscpd.json` in the project root, or a `jscpd` key in `package.json`
— and when it finds one it stands aside and lets jscpd read it.

So this project's `path: ["lib"]` decides what is scanned, and the shipped
`path: ["src"]` never gets a say: the clone under `lib` is reported and the one
under `src` is not. `lib` is relative, and resolves against the project.

jscpd honours `.gitignore`, walking up until it finds a repository — so the case
is its own, as a real project is. Without that it would walk out into
habit-hooks' checkout, whose `.gitignore` covers the very directory these cases
run in, and jscpd would scan nothing.

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

```bash
git init -q
```

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["**/*.ts"]

[sensors.line-count]
disabled = true
```

📄.jscpd.json
```json
{
  "path": ["lib"],
  "minLines": 5,
  "minTokens": 50
}
```

📄src/a.ts
```typescript
export function alpha(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient };
}
```

📄src/b.ts
```typescript
export function beta(x: number, y: number) {
  const sum = x + y;
  const product = x * y;
  const diff = x - y;
  const quotient = x / y;
  const scaled = sum * product;
  return { sum, product, diff, quotient };
}
```

📄lib/c.ts
```typescript
export function gamma(a: number, b: number) {
  const total = a + b;
  const scaled = a * b;
  const gap = a - b;
  const ratio = a / b;
  const mixed = total * scaled;
  return { total, scaled, gap, ratio, mixed };
}
```

📄lib/d.ts
```typescript
export function delta(a: number, b: number) {
  const total = a + b;
  const scaled = a * b;
  const gap = a - b;
  const ratio = a / b;
  const mixed = total * scaled;
  return { total, scaled, gap, ratio, mixed };
}
```

```bash
habit-sensors --all | jq '[.[] | {smell, files: [.issues[].key]}]'
```

🖥️ ✅
```json
[
  {
    "smell": "duplicated-code",
    "files": [
      "lib/c.ts",
      "lib/d.ts"
    ]
  }
]
```
