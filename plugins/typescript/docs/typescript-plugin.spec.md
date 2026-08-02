# The typescript plugin — acceptance

The typescript plugin runs its sensors through the real `habit-sensors` pipeline.
These cases run the **actual** tools (`eslint`, `knip`, and a `ts-morph` comment
scan) against a fixture with a known smell and assert the canonical finding comes
out, mapped to the smell keys in [smell-vocabulary.md](smell-vocabulary.md).

`habit-sensors` is the installed CLI. The Node tools live in the typescript
plugin's own `node_modules` (`plugins/typescript/node_modules`). The intro
symlinks that into each case as `./node_modules` and puts its `.bin` on `PATH`
once — the shipped `eslint.config.mjs` and `knip` resolve their plugin deps
through the normal `node_modules` walk (ESM `import` ignores `NODE_PATH`, which
is why we symlink rather than set it), and `ts-morph`'s `require` resolves the
same way. The cases share `finding.jq` to project each finding down to the
asserted fields.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]
```

📄package.json
```json
{ "name": "demo", "version": "0.0.0" }
```

📄finding.jq
```jq
sort_by(.smell)[]
| {
    smell,
    language,
    key: (.issues[0].key | sub(".*/"; "")),
    line: .issues[0].details.line,
    source: .issues[0].details.source
  }
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## The eslint adapter

The `eslint` adapter runs eslint with the shipped flat config and a jq transform
in its command flattens the per-file `messages[]`, remaps each rule ID to a
canonical smell, and groups one finding per smell, stamping `source:
"eslint:<rule>"` on each issue.

A message eslint raises about a *file* rather than about a rule carries
`ruleId: null` — an ignored file in the scope, an `eslint-disable` directive
nothing used. Indexing the smell map with that null is a jq **error**, not a
miss, so it would kill the sensor and silently take every eslint smell in the
run with it. The adapter drops those messages before the map sees them, and
passes `--no-warn-ignored` so the commonest of them is never raised at all. A
`fatal` message is the one exception: it has no rule ID either and is exactly
what `parse-error` exists to report, so it is kept.

📄eslint.config.mjs @plugins/typescript/src/habit_hooks_typescript/eslint.config.mjs

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.knip]
disabled = true

[sensors.comment]
disabled = true
```

### Rule IDs map to canonical smells

The config caps `max-params` at 3, so a four-parameter function trips
`max-params` → `too-many-parameters`.

📄src/billing.ts
```typescript
export function charge(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
```

```bash
habit-sensors --all | jq -f finding.jq
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "language": "typescript",
  "key": "billing.ts",
  "line": 1,
  "source": "eslint:max-params"
}
```

### A file the eslint config ignores costs the run nothing

The scope hands the sensor every `*.ts` file the project has, including ones the
project's own eslint config ignores — the shipped config ignores
`tests/fixtures/**`. Eslint's "File ignored because of a matching ignore
pattern" notice is not a smell and must not become one; the real smell next to
it still reports.

📄src/billing.ts
```typescript
export function charge(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
```

📄tests/fixtures/legacy.ts
```typescript
export const legacy = 1;
```

```bash
habit-sensors --all | jq -f finding.jq
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "language": "typescript",
  "key": "billing.ts",
  "line": 1,
  "source": "eslint:max-params"
}
```

### An unused eslint-disable directive is dropped, not mapped

`--no-warn-ignored` removes one source of rule-less messages, not the class.
Eslint reports an `eslint-disable` directive that suppressed nothing the same
way — `ruleId: null`, not fatal — so the adapter has to drop it on its own
merits. The `eqeqeq` violation in the same file is the finding that survives.

📄src/compare.ts
```typescript
// eslint-disable-next-line eqeqeq
export const version = 1;

export function isZero(value: number): boolean {
  return value == 0;
}
```

```bash
habit-sensors --all | jq -f finding.jq
```

🖥️ ✅
```json
{
  "smell": "loose-equality",
  "language": "typescript",
  "key": "compare.ts",
  "line": 5,
  "source": "eslint:eqeqeq"
}
```

### A file eslint cannot parse is reported as parse-error

The one rule-less message that *is* a smell. Eslint marks it `fatal`, and the
adapter keeps it and maps it to `parse-error`, sourced `eslint:fatal` because
there is no rule to name.

📄src/broken.ts
```typescript
export function broken(: number {
```

```bash
habit-sensors --all | jq -f finding.jq
```

🖥️ ✅
```json
{
  "smell": "parse-error",
  "language": "typescript",
  "key": "broken.ts",
  "line": 1,
  "source": "eslint:fatal"
}
```

### A rule the smell map does not know passes through as itself

A project that adds its own rules to the config still gets findings for them —
an unmapped rule ID becomes the smell verbatim. The mapper has no guide for it,
so it reports uncoached rather than disappearing.

📄eslint.config.mjs
```javascript
export default [
  { files: ["**/*.ts"], rules: { "no-console": "error" } },
];
```

📄src/log.ts
```typescript
console.log("shipping this by accident");
```

```bash
habit-sensors --all | jq -f finding.jq
```

🖥️ ✅
```json
{
  "smell": "no-console",
  "language": "typescript",
  "key": "log.ts",
  "line": 1,
  "source": "eslint:no-console"
}
```

## knip sensor maps an unused export to unused-export

The `knip` sensor runs knip with the shipped `knip.json`, accepts its 0/1 exit
codes, and shapes each typed issue array into a finding — `exports` →
`unused-export`, one issue per symbol keyed by the symbol name. `helper.ts`
exports `neverUsed`, which nothing imports.

📄knip.json @plugins/typescript/src/habit_hooks_typescript/knip.json

📄src/cli.ts
```typescript
import { used } from "./helper";

used();
```

📄src/helper.ts
```typescript
export function used(): void {}

export function neverUsed(): void {}
```

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.eslint]
disabled = true

[sensors.comment]
disabled = true
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "unused-export",
  "language": "typescript",
  "key": "neverUsed",
  "file": "src/helper.ts",
  "source": "knip:exports"
}
```

## comment sensor maps a non-essential comment to non-essential-comment

The `comment` sensor scans the scoped files with ts-morph and reports comments
the reader could work out from the code, shaping each into a
`non-essential-comment` finding with `source: "comment:non-essential"`.

📄src/util.ts
```typescript
export function add(a: number, b: number): number {
  // this comment restates what the code already says clearly
  return a + b;
}
```

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.eslint]
disabled = true

[sensors.knip]
disabled = true
```

```bash
habit-sensors --all | jq -f finding.jq
```

🖥️ ✅
```json
{
  "smell": "non-essential-comment",
  "language": "typescript",
  "key": "util.ts",
  "line": 2,
  "source": "comment:non-essential"
}
```
