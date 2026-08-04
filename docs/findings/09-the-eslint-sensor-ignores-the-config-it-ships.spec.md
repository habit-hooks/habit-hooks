# 09. The eslint sensor ignores the config it ships

The typescript plugin ships `eslint.config.mjs`: a complete flat config with the
thresholds the plugin's smells are defined against — `max-params: 3`,
`max-depth: 4`, `complexity: 10`, `max-lines-per-function: 12`. The sensor that
runs eslint never mentions it:

```text
$ grep -c -- --config plugins/typescript/src/habit_hooks_typescript/sensors/eslint.toml
0
```

So eslint discovers whatever the consumer has, and three things follow from that
one omission. A project with no flat config of its own gets nothing but an error
(the plugin's own config is sitting right there, unused). A project that copies
the shipped config gets a rule pairing that is wrong for TypeScript and reports
interface method parameters as unused variables, at error severity. And a project
that instead follows typescript-eslint's own documented setup gets its findings
under a raw rule ID, because the sensor's smell map carries three
`@typescript-eslint/*` rules and not that one.

Three defects, one root: the sensor does not use the config it ships, so the
config is never the thing being tested and the map was never lined up with it.
One case each below.

The Node tools live in `plugins/typescript/node_modules`; the intro symlinks that
into each case as `./node_modules` and puts its `.bin` on `PATH` once. Only the
eslint sensor runs here.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.knip]
disabled = true

[sensors.comment]
disabled = true
```

📄package.json
```json
{ "name": "demo", "version": "0.0.0" }
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## Today

### A project with no flat config of its own gets an eslint error instead of findings

Delete this case when the fix lands.

The project is a plain TypeScript project that has just installed habit-hooks and
the tools the README names. It has a four-parameter function, which the shipped
config's `max-params: 3` exists to catch. What comes back is the incomplete-run
finding and eslint's "couldn't find a config" complaint — the typescript plugin
catches nothing at all until the consumer authors a flat config, which no
document tells them to do.

📄src/billing.ts
```typescript
export function charge(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
```

```bash
habit-sensors --all >out.json 2>err.txt; echo "exit=$?"
jq -c 'map(.smell)' out.json
grep -oF "ESLint couldn't find an eslint.config.(js|mjs|cjs) file." err.txt
```

🖥️ ✅
```text
exit=1
["incomplete-run"]
ESLint couldn't find an eslint.config.(js|mjs|cjs) file.
```

The config the run needed ships inside the plugin, and the sensor's command never
names it:

```bash
test -f ../../plugins/typescript/src/habit_hooks_typescript/eslint.config.mjs && echo "shipped: eslint.config.mjs"
grep -c -- "--config" ../../plugins/typescript/src/habit_hooks_typescript/sensors/eslint.toml || true
```

🖥️ ✅
```text
shipped: eslint.config.mjs
0
```

### The shipped config reports interface method parameters as unused variables

Delete this case when the fix lands.

This case runs the shipped `eslint.config.mjs` verbatim. It turns the base
`no-unused-vars` on and `@typescript-eslint/no-unused-vars` off — backwards for
TypeScript, where the base rule does not understand type positions. An interface
that declares two method signatures has no unused anything; the parameter names
are documentation, and removing them is not even valid TypeScript. The run
reports two `unused-variable` issues, and eslint's own severity for them is `2`:
errors, enforced, failing the build. The toy study collected three.

📄eslint.config.mjs @plugins/typescript/src/habit_hooks_typescript/eslint.config.mjs

📄src/repository.ts
```typescript
export interface Repository {
  save(item: string): void;
  find(id: string): string;
}
```

```bash
habit-sensors --all 2>/dev/null | jq -c '[.[] | {smell, source: .issues[0].details.source, names: [.issues[].details.message | split(" ")[0]], lines: [.issues[].details.line]}]'
eslint -f json --no-warn-ignored src/repository.ts > eslint.json || true
jq -c '[.[0].messages[] | {ruleId, severity}]' eslint.json
```

🖥️ ✅
```text
[{"smell":"unused-variable","source":"eslint:no-unused-vars","names":["'item'","'id'"],"lines":[2,3]}]
[{"ruleId":"no-unused-vars","severity":2},{"ruleId":"no-unused-vars","severity":2}]
```

### A project on typescript-eslint's documented setup gets an uncoached key

Delete this case when the fix lands.

The other side of the same pairing. This project does what typescript-eslint
documents — base rule off, `@typescript-eslint/no-unused-vars` on — and gets the
right answer from eslint: the interface parameters are silent, the genuinely
unused `unusedTax` is reported. But the sensor's smell map does not carry that
rule ID, so the finding lands under the raw rule name instead of
`unused-variable`: no guide, no coaching, and a snooze key that does not match the
one the same smell has anywhere else in the vocabulary. Verified in the field by
probing OpenBoard with a temporary unused variable — `unused-variable#…` became
`@typescript-eslint/no-unused-vars#…`.

📄eslint.config.mjs
```javascript
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";

export default [
  {
    files: ["**/*.ts"],
    languageOptions: { parser: tsparser },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": "error",
    },
  },
];
```

📄src/repository.ts
```typescript
export interface Repository {
  save(item: string): void;
}

export function total(prices: number[]): number {
  const unusedTax = 0.2;
  return prices.length;
}
```

```bash
habit-sensors --all 2>/dev/null | jq -c '[.[] | {smell, source: .issues[0].details.source, names: [.issues[].details.message | split(" ")[0]], lines: [.issues[].details.line]}]'
grep -c "@typescript-eslint/no-unused-vars" ../../plugins/typescript/src/habit_hooks_typescript/sensors/eslint.toml || true
```

🖥️ ✅
```text
[{"smell":"@typescript-eslint/no-unused-vars","source":"eslint:@typescript-eslint/no-unused-vars","names":["'unusedTax'"],"lines":[6]}]
0
```

## Wanted

The sensor runs the config the plugin ships, so that config is what the plugin's
thresholds mean and what these specs test. A consumer with their own flat config
still wins — pointing the sensor at it is a one-line override, the same way every
other shipped default is replaceable — but no consumer has to author one before
the plugin does anything.

With the config actually in use, its rule pairing has to be right for TypeScript:
base `no-unused-vars` off, `@typescript-eslint/no-unused-vars` on, which is what
typescript-eslint documents and what stops type positions being read as code. And
the smell map has to name the rule that then does the reporting, or the fix moves
the finding out of the vocabulary instead of into it.

### The plugin's own config is what runs when the project has none 🟡

The same four-parameter function as the Today case, in the same config-less
project. The shipped `max-params: 3` catches it.

📄src/billing.ts
```typescript
export function charge(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, key: .issues[0].key, source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"too-many-parameters","key":"src/billing.ts","source":"eslint:max-params"}]
```

### A project's own flat config still wins 🟡

Overriding a shipped default must stay a one-liner. A project that names its own
config in `.habit-hooks/config.toml` gets exactly that config, and the rule it
adds reports as itself.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.knip]
disabled = true

[sensors.comment]
disabled = true

[sensors.eslint]
args = ["--config", "eslint.config.mjs"]
```

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
habit-sensors --all | jq -c '[.[] | {smell, key: .issues[0].key, source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"no-console","key":"src/log.ts","source":"eslint:no-console"}]
```

### The shipped config is silent on interface method parameters 🟡

The pairing fixed: type positions are no longer read as unused variables, and a
real unused variable in the same file still reports — as `unused-variable`, the
canonical smell, whichever of the two rules did the reporting.

📄src/repository.ts
```typescript
export interface Repository {
  save(item: string): void;
  find(id: string): string;
}

export function total(prices: number[]): number {
  const unusedTax = 0.2;
  return prices.length;
}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, names: [.issues[].details.message | split(" ")[0]], lines: [.issues[].details.line]}]'
```

🖥️ ✅
```text
[{"smell":"unused-variable","names":["'unusedTax'"],"lines":[7]}]
```

### The smell map covers the TypeScript unused-vars rule 🟡

A project running typescript-eslint's documented pairing gets the canonical smell,
its guide, and a snooze key that matches the one every other unused variable has.

📄eslint.config.mjs
```javascript
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";

export default [
  {
    files: ["**/*.ts"],
    languageOptions: { parser: tsparser },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": "error",
    },
  },
];
```

📄src/repository.ts
```typescript
export function total(prices: number[]): number {
  const unusedTax = 0.2;
  return prices.length;
}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-variable","source":"eslint:@typescript-eslint/no-unused-vars"}]
```
