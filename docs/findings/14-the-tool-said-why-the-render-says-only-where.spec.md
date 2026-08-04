# 14. The tool said why; the render says only where

Every sensor that wraps a real linter captures the tool's own message. The eslint
adapter puts it on each issue as `details.message`; so does the ts-morph comment
sensor. Nothing ever renders it. Both shared listings
([guide-includes.spec.md](../guide-includes.spec.md)) print `file:line` and then
`content` — and `content` is a field neither sensor emits. So the message is
carried the whole length of the pipeline and dropped at the last step.

What the finding holds:

```text
Function 'buildOrder' has too many parameters (8). Maximum allowed is 3.
```

What the agent is shown:

```text
src/orders/order-service.ts:8
```

The agent cannot act on that without re-opening the file, and when two smells
fire on the same declaration it is shown the *same line twice* with nothing to
say which block means what. The README's own "Sample output" is richer than what
ships — it shows `bill(customer, items, discount, tax) has 4 parameters` under
the location — so the shipped render is behind its own advertisement.

This is not an argument for stuffing the message into `content`.
[guide-includes.spec.md](../guide-includes.spec.md) is deliberate that `content`
is *not* the linter's message: repeated boilerplate down a listing says little,
whereas lined-up signatures expose a shared shape. The finding is that the render
shows **neither** — the sensors emit no `content`, and the `message` they do emit
is thrown away, so the listing carries no facts at all.

Two duplication defects ride along, both observed in a real run and both pinned
below: one file reported **twice** as `oversized-file` because two sensors
measure it, and identical `file:line` entries repeating inside a single smell so
the banner says "2 issues" over one visible location.

These cases run the real `eslint` and `line-count` sensors, because the finding
is about what a real tool says and what the render does with it. The Node tools
come from the typescript plugin's own `node_modules`, symlinked in and put on
`PATH` exactly as
[typescript-plugin.spec.md](../../plugins/typescript/docs/typescript-plugin.spec.md)
does. `knip`, `comment` and `jscpd` are switched off so each case shows one
mechanism.

📄package.json
```json
{ "name": "demo", "version": "0.0.0" }
```

📄eslint.config.mjs @plugins/typescript/src/habit_hooks_typescript/eslint.config.mjs

📄.habit-hooks/config.toml
```toml
plugins = ["typescript", "generic"]

[sensors.knip]
disabled = true

[sensors.comment]
disabled = true

[sensors.jscpd]
disabled = true
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## Today

### The sensor captures eslint's message and the render drops it

Delete this case when the fix lands.

`buildOrder` takes eight parameters in a thirteen-line body, so eslint reports
both `max-params` and `max-lines-per-function`. Each message states the number
that was measured and the number allowed.

📄src/orders/order-service.ts
```typescript
export interface Order {
  id: string;
  customer: string;
  currency: string;
  amount: number;
}

export function buildOrder(
  id: string,
  customer: string,
  currency: string,
  total: number,
  discount: number,
  tax: number,
  shipping: number,
  giftWrap: boolean,
): Order {
  const amount = total - discount + tax + shipping + (giftWrap ? 5 : 0);
  return { id, customer, currency, amount };
}
```

The findings carry both messages:

```bash
habit-sensors --all | jq -c '.[] | {smell, message: .issues[0].details.message}'
```

🖥️ ✅
```json
{"smell":"oversized-function","message":"Function 'buildOrder' has too many lines (13). Maximum allowed is 12."}
{"smell":"too-many-parameters","message":"Function 'buildOrder' has too many parameters (8). Maximum allowed is 3."}
```

Rendered, stripped to its banners and listings, the two blocks are
indistinguishable — the same location under each, and neither number survives.
Everything between them is coaching prose that never names this function:

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── oversized-function (1 issue) ──
src/orders/order-service.ts:8
── too-many-parameters (1 issue) ──
src/orders/order-service.ts:8
```

### One file is reported twice as `oversized-file`

Delete this case when the fix lands.

`oversized-file` has two producers: eslint's `max-lines` (typescript plugin) and
the `line-count` sensor (generic plugin), both capped at 200. A project running
both plugins — the documented way to get `oversized-file` for a TypeScript
project — gets the file named twice, in two banners, with the full guide printed
in between each time.

```bash
mkdir -p src &&
  { echo "export const first = 1;"; for i in $(seq 2 205); do echo "export const pad$i = $i;"; done; } > src/registry.ts
```

Two findings, same smell, same file, from two sensors:

```bash
habit-sensors --all | jq -c '.[] | {smell, key: .issues[0].key, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{"smell":"oversized-file","key":"src/registry.ts","source":"eslint:max-lines"}
{"smell":"oversized-file","key":"src/registry.ts","source":"line-count"}
```

And the render says the same thing twice, byte for byte:

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── oversized-file (1 issue) ──
src/registry.ts
── oversized-file (1 issue) ──
src/registry.ts
```

### Identical `file:line` entries repeat inside one smell

Delete this case when the fix lands.

A curried factory puts two arrow functions on the same line, and both bodies run
past twelve lines, so eslint reports `max-lines-per-function` twice at line 1 —
distinguished only by column, which the listing does not print. The banner
promises two issues and shows one location.

📄src/handler.ts
```typescript
export const createHandler = (label: string) => (input: number[]): string => {
  const doubled = input.map((n) => n * 2);
  const tripled = input.map((n) => n * 3);
  const total = doubled.reduce((sum, n) => sum + n, 0);
  const other = tripled.reduce((sum, n) => sum + n, 0);
  const parts: string[] = [];
  parts.push(label);
  parts.push(String(total));
  parts.push(String(other));
  parts.push(String(input.length));
  parts.push(String(doubled.length));
  parts.push(String(tripled.length));
  parts.push("done");
  return parts.join(",");
};
```

The two issues differ only in `column`:

```bash
habit-sensors --all | jq -c '[.[0].issues[] | {line: .details.line, column: .details.column}]'
```

🖥️ ✅
```json
[{"line":1,"column":46},{"line":1,"column":75}]
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── oversized-function (2 issues) ──
src/handler.ts:1
src/handler.ts:1
```

## Wanted

The message is already in the finding; the render just has to use it. Nothing
about the long-form coaching changes — the prose above the listing stays exactly
as it is, because that is what teaches the agent *why*. What changes is that the
listing under it stops being a bare coordinate and starts carrying the fact the
tool measured, so an agent can decide what to do without re-opening the file.

Alongside that, two duplications go away: one `oversized-file` finding per file
whichever sensors measured it, and no location printed twice inside one smell.

### The message renders with each issue 🟡

Same eight-parameter function. Each listing line now says what the tool found, so
the two blocks are told apart at a glance.

📄src/orders/order-service.ts
```typescript
export interface Order {
  id: string;
  customer: string;
  currency: string;
  amount: number;
}

export function buildOrder(
  id: string,
  customer: string,
  currency: string,
  total: number,
  discount: number,
  tax: number,
  shipping: number,
  giftWrap: boolean,
): Order {
  const amount = total - discount + tax + shipping + (giftWrap ? 5 : 0);
  return { id, customer, currency, amount };
}
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── oversized-function (1 issue) ──
src/orders/order-service.ts:8  Function 'buildOrder' has too many lines (13). Maximum allowed is 12.
── too-many-parameters (1 issue) ──
src/orders/order-service.ts:8  Function 'buildOrder' has too many parameters (8). Maximum allowed is 3.
```

### One `oversized-file` finding per file, whoever measured it 🟡

Two sensors, one answer. The file is named once, and the guide is printed once.

```bash
mkdir -p src &&
  { echo "export const first = 1;"; for i in $(seq 2 205); do echo "export const pad$i = $i;"; done; } > src/registry.ts
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── oversized-file (1 issue) ──
src/registry.ts
```

### Two issues on the same line are told apart 🟡

Two distinct functions really do start at line 1, so neither may be dropped —
but the render has to show the reader that they are two. The column is the only
discriminator eslint gives, so the listing prints it.

📄src/handler.ts
```typescript
export const createHandler = (label: string) => (input: number[]): string => {
  const doubled = input.map((n) => n * 2);
  const tripled = input.map((n) => n * 3);
  const total = doubled.reduce((sum, n) => sum + n, 0);
  const other = tripled.reduce((sum, n) => sum + n, 0);
  const parts: string[] = [];
  parts.push(label);
  parts.push(String(total));
  parts.push(String(other));
  parts.push(String(input.length));
  parts.push(String(doubled.length));
  parts.push(String(tripled.length));
  parts.push("done");
  return parts.join(",");
};
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── oversized-function (2 issues) ──
src/handler.ts:1:46  Arrow function has too many lines (15). Maximum allowed is 12.
src/handler.ts:1:75  Arrow function has too many lines (15). Maximum allowed is 12.
```

### Genuinely identical issues collapse to one 🟡

When two issues are identical in every rendered field there is nothing for the
reader to tell apart, and the count must not inflate. A fixture sensor emits the
same issue twice; the render shows one line and says one issue.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["twice"]
```

📄.habit-hooks/generic/sensors/twice.toml
```toml
command = "cat ${dir}/twice.json"
```

📄.habit-hooks/generic/sensors/twice.json
```json
[{"smell":"unused-variable","details":{},"issues":[
  {"key":"src/a.ts:4","details":{"file":"src/a.ts","line":4,"message":"'total' is assigned a value but never used."}},
  {"key":"src/a.ts:4","details":{"file":"src/a.ts","line":4,"message":"'total' is assigned a value but never used."}}]}]
```

📄src/a.ts
```typescript
export const a = 1;
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── unused-variable (1 issue) ──
src/a.ts:4  'total' is assigned a value but never used.
```
