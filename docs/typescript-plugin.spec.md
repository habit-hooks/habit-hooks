# The typescript plugin — acceptance

The typescript plugin runs its sensors through the real `habit-sensors` pipeline.
These cases run the **actual** tools (`eslint`, `knip`, and a `ts-morph` comment
scan) against a fixture with a known smell and assert the canonical finding comes
out, mapped to the smell keys in [smell-vocabulary.md](smell-vocabulary.md).

`habit-sensors` is the installed CLI. The Node tools live in the repo's
`node_modules` (two dirs up from a case dir), so each invocation puts that
`node_modules/.bin` on `PATH` and exposes it as `NODE_PATH` so `eslint`, `knip`,
and `ts-morph` resolve from the temp fixture.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]
```

📄package.json
```json
{ "name": "demo", "version": "0.0.0" }
```

## eslint adapter maps rule IDs to canonical smells

The `eslint` adapter runs eslint with the shipped flat config and a jq transform
in its command flattens the per-file `messages[]`, remaps each rule ID to a
canonical smell, and groups one finding per smell, stamping `source:
"eslint:<rule>"` on each issue. The config caps `max-params` at 3, so a
four-parameter function trips `max-params` → `too-many-parameters`.

📄eslint.config.mjs @plugins/typescript/eslint.config.mjs

📄src/billing.ts
```typescript
export function charge(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
```

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.knip]
disabled = true

[sensors.comment]
disabled = true
```

```bash
PATH="$PWD/../../node_modules/.bin:$PATH" NODE_PATH="$PWD/../../node_modules" habit-sensors --all | jq -c 'sort_by(.smell)[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{"smell":"too-many-parameters","language":"typescript","key":"billing.ts","line":1,"source":"eslint:max-params"}
```

## knip sensor maps an unused export to unused-export

The `knip` sensor runs knip with the shipped `knip.json`, accepts its 0/1 exit
codes, and shapes each typed issue array into a finding — `exports` →
`unused-export`, one issue per symbol keyed by the symbol name. `helper.ts`
exports `neverUsed`, which nothing imports.

📄knip.json @plugins/typescript/knip.json

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
PATH="$PWD/../../node_modules/.bin:$PATH" NODE_PATH="$PWD/../../node_modules" habit-sensors --all | jq -c '.[] | {smell, language, key: .issues[0].key, file: .issues[0].details.file, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{"smell":"unused-export","language":"typescript","key":"neverUsed","file":"src/helper.ts","source":"knip:exports"}
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
PATH="$PWD/../../node_modules/.bin:$PATH" NODE_PATH="$PWD/../../node_modules" habit-sensors --all | jq -c '.[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{"smell":"non-essential-comment","language":"typescript","key":"util.ts","line":2,"source":"comment:non-essential"}
```
