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
`duplicated-code` finding listing both occurrences in `issues`. The plugin ships
`.jscpd.json` (`path: ["src"]`, `minLines: 5`, `minTokens: 50`, `threshold: 0`),
so jscpd scans `src` and reports the duplicated block.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]

[sensors.line-count]
disabled = true
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
