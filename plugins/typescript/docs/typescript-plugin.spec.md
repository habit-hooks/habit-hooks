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

## knip sensor

The `knip` sensor runs knip with the shipped `knip.json` and shapes its JSON into
findings. Unused files come from knip's top-level `files` array, not from an issue
row; `classMembers`/`enumMembers` arrive as object maps and are flattened; any key
the plugin does not coach (`types`, …) passes through under its own name rather
than vanishing.

The shipped `knip.json` marks production patterns with a trailing `!` on both
`entry` and `project`, which gates a second `knip --production` pass. The default
pass is authoritative for every issue type; the `--production` pass contributes
only the dead code the default pass did not already name — code alive solely
because a test references it — as the separate `test-only-dead-code` smell, so its
coaching can say "delete the test too".

Every case here disables the other two sensors and ships the plugin's real
`knip.json`. A case that needs a different knip config re-declares it.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.eslint]
disabled = true

[sensors.comment]
disabled = true
```

📄knip.json @plugins/typescript/src/habit_hooks_typescript/knip.json

### An unused export maps to unused-export

`helper.ts` exports `neverUsed`, which nothing imports — one issue per symbol,
keyed by the symbol name, sourced `knip:exports`.

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

### An unreferenced file maps to unused-file

`orphan.ts` is imported by nothing, so knip lists it in the top-level `files`
array. Read from there — never from an issue row — it becomes `unused-file`,
keyed by the file, sourced `knip:files`. This is the headline smell the old
sensor could never fire.

📄src/cli.ts
```typescript
import { used } from "./helper";

used();
```

📄src/helper.ts
```typescript
export function used(): void {}
```

📄src/orphan.ts
```typescript
export function orphanFn(): void {}
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "unused-file",
  "language": "typescript",
  "key": "src/orphan.ts",
  "file": "src/orphan.ts",
  "source": "knip:files"
}
```

### An unused class member maps to unused-class-member

knip reports class members as an object map keyed by the parent symbol, which the
old sensor called `.map()` on and crashed. Flattened, `Widget.unusedMethod`
becomes `unused-class-member`. This case ships its own `knip.json` that opts into
member analysis.

📄knip.json
```json
{
  "entry": ["src/cli.ts!"],
  "project": ["src/**/*.ts!"],
  "ignore": ["dist/**"],
  "include": ["classMembers"]
}
```

📄src/helper.ts
```typescript
export function used(): void {}

export class Widget {
  usedMethod(): void {}

  unusedMethod(): void {}
}
```

📄src/cli.ts
```typescript
import { used, Widget } from "./helper";

used();
const w = new Widget();
w.usedMethod();
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "unused-class-member",
  "language": "typescript",
  "key": "unusedMethod",
  "file": "src/helper.ts",
  "source": "knip:classMembers"
}
```

### A knip issue type outside the map passes through uncoached

An unused *type* export lands under knip's `types` key, which the plugin does not
map to a canonical smell. It surfaces under its own name (`types`, sourced
`knip:types`) rather than being silently discarded — the same pass-through the
eslint adapter gives an unmapped rule ID.

📄src/cli.ts
```typescript
import { used } from "./helper";

used();
```

📄src/helper.ts
```typescript
export function used(): void {}

export type NeverUsedType = { a: number };
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "types",
  "language": "typescript",
  "key": "NeverUsedType",
  "file": "src/helper.ts",
  "source": "knip:types"
}
```

### Code reachable only by a test is test-only dead code, not plainly unused

`testOnly` is exported by production code and imported only by a top-level test.
Because the shipped config lists `tests/**` as an unmarked `entry` (not `ignore`),
the default pass sees the test's reference and reports nothing. The gated
`--production` pass drops that reference and finds `testOnly` dead — surfaced as
`test-only-dead-code`, the smell whose guide says to remove the test as well, and
**not** as a plain `unused-export`.

📄src/helper.ts
```typescript
export function prodUsed(): void {}

export function testOnly(): void {}
```

📄src/cli.ts
```typescript
import { prodUsed } from "./helper";

prodUsed();
```

📄tests/helper.test.ts
```typescript
import { testOnly } from "../src/helper";

testOnly();
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "test-only-dead-code",
  "language": "typescript",
  "key": "testOnly",
  "file": "src/helper.ts",
  "source": "knip:production:exports"
}
```

### The production pass never reports a test file as dead

The `--production` pass ignores test entries, so a `.spec.ts` file reachable only
through a `.test.ts` entry looks like an unused file to it (the default pass, with
the test as an entry, sees it as reachable). Reporting it would invite an agent to
delete real coverage, so a test file is guarded out of the production pass's
findings — the run is clean.

📄knip.json
```json
{
  "entry": ["src/cli.ts!", "src/**/*.test.ts"],
  "project": ["src/**/*.ts!"],
  "ignore": ["dist/**"]
}
```

📄src/helper.ts
```typescript
export function prodUsed(): void {}
```

📄src/cli.ts
```typescript
import { prodUsed } from "./helper";

prodUsed();
```

📄src/thing.spec.ts
```typescript
export function specHelper(): void {}
```

📄src/thing.test.ts
```typescript
import { specHelper } from "./thing.spec";

specHelper();
```

```bash
habit-sensors --all | jq -c 'map(.smell) | sort'
```

🖥️ ✅
```json
[]
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
