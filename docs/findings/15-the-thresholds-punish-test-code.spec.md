# 15. The thresholds punish test code

`max-lines-per-function: 12` is measured on every function eslint can see, and a
`describe()` callback is a function. Its body includes the bodies of every
`it()` nested inside it, so the counter charges a test file for the one thing
good test files do: group related scenarios under a shared label.

Three one-line assertions under one `describe` is thirteen lines, and thirteen is
over twelve:

```text
── oversized-function (1 issue) ──
…
tests/total.test.ts:4
```

There is no single-responsibility refactor available for "group these three
scenarios under one label". A field study's agent hit this during real feature
work and split one `describe` into three sibling `describe` blocks purely to get
under the counter. Its own words: **"threshold appeasement, not better tests"** —
the test output now reads as three unrelated groups instead of one subject with
three cases. 5 of the 17 hits in that study's toy repo were `it()`/`describe()`
bodies.

The sharp end is that the guide the agent is handed *warns against exactly the
move it then has to make*: "Avoid mechanical extraction. Pulling out a `helperA`
/ `helperB` purely to satisfy the threshold often hides the smell behind worse
names and leaves the real shape untouched." That advice is right, and it is
unusable here — the agent is told not to do the only thing that will clear the
finding. Coaching that cannot be followed teaches an agent to stop reading
coaching.

These cases run the real `eslint` sensor, because the finding is about what
eslint's own counter measures. The Node tools come from the typescript plugin's
`node_modules`, symlinked in and put on `PATH` as
[typescript-plugin.spec.md](../../plugins/typescript/docs/typescript-plugin.spec.md)
does; `knip`, `comment` and `jscpd` are off so each case shows one mechanism.

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

### An ordinary vitest file with one describe and three its is blocked

Delete this case when the fix lands.

Nothing here is unusual: one subject, three cases, one assertion each, a blank
line between them. The `describe` callback spans thirteen lines and the run
fails. The whole guide is asserted, because the guide is the finding: paragraph
three tells the agent not to make the only change that will clear this.

📄tests/total.test.ts
```typescript
import { describe, expect, it } from "vitest";
import { total } from "../src/total";

describe("total", () => {
  it("sums an empty basket to zero", () => {
    expect(total([])).toBe(0);
  });

  it("sums a single price", () => {
    expect(total([12])).toBe(12);
  });

  it("sums several prices", () => {
    expect(total([1, 2, 3])).toBe(6);
  });
});
```

```bash
habit-sensors --all | jq -c '.[] | {smell, line: .issues[0].details.line, message: .issues[0].details.message}'
```

🖥️ ✅
```json
{"smell":"oversized-function","line":4,"message":"Arrow function has too many lines (13). Maximum allowed is 12."}
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ❌ 1
```text
── oversized-function (1 issue) ──

Functions over 12 lines almost always carry more than one responsibility, and that is the smell to chase — not the line count itself.

Analyse responsibilities first: what distinct concerns does this function handle? Ask: (1) Are these separate responsibilities that belong in different methods? (2) Should this become a class with multiple methods? (3) Can you group cohesive data into objects to reduce local variables?

Avoid mechanical extraction. Pulling out a `helperA` / `helperB` purely to satisfy the threshold often hides the smell behind worse names and leaves the real shape untouched. Find true responsibility boundaries.

If responsibilities are tangled you may need to first *inline* methods to see the whole picture before redistributing. Think of this when reducing line count seems particularly hard — stepping backwards often opens up better possibilities.

A concrete technique: write what the method does in one short sentence. Refactor until the code reads as close to that sentence as possible. If you cannot say what it does in one sentence, it almost certainly has more than one responsibility.

tests/total.test.ts:4
```

### Splitting the group into three is what makes it pass

Delete this case when the fix lands.

The same three tests, the same three assertions, not one line of behaviour
changed — only the grouping broken up so no callback exceeds twelve lines. The
gate now says the change is clean and hands the agent the pass reminder. This is
the case that makes the finding a defect rather than a preference: the tool pays
for worse test structure and is silent about better.

📄tests/total.test.ts
```typescript
import { describe, expect, it } from "vitest";
import { total } from "../src/total";

describe("total with no prices", () => {
  it("sums an empty basket to zero", () => {
    expect(total([])).toBe(0);
  });
});

describe("total with one price", () => {
  it("sums a single price", () => {
    expect(total([12])).toBe(12);
  });
});

describe("total with several prices", () => {
  it("sums several prices", () => {
    expect(total([1, 2, 3])).toBe(6);
  });
});
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

### A single test with an ordinary arrange/act/assert body trips it too

Delete this case when the fix lands.

Dropping `describe` is not the escape either. One `it`, one basket, one call,
six assertions on the receipt — the shape every testing guide recommends — is
thirteen lines and blocks the run on its own.

📄tests/receipt.test.ts
```typescript
import { expect, it } from "vitest";
import { checkout } from "../src/checkout";

it("charges a loyal customer the discounted total", () => {
  const basket = [
    { sku: "A", price: 10, quantity: 2 },
    { sku: "B", price: 5, quantity: 1 },
  ];
  const receipt = checkout(basket, { loyalty: true });
  expect(receipt.lines).toHaveLength(2);
  expect(receipt.subtotal).toBe(25);
  expect(receipt.discount).toBe(2.5);
  expect(receipt.total).toBe(22.5);
  expect(receipt.currency).toBe("EUR");
  expect(receipt.giftWrapped).toBe(false);
});
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^tests/'
```

🖥️ ❌ 1
```text
── oversized-function (1 issue) ──
tests/receipt.test.ts:4
```

### The counter cannot tell a real helper from the grouping

Delete this case when the fix lands.

This file has both: a fourteen-line `buildBasket` helper that genuinely wants
attention, and a thirteen-line `describe` callback that does not. They arrive in
one listing, ranked equally, with nothing to separate them — so the real finding
is one line away from the noise, and both cost the same to silence.

📄tests/basket.test.ts
```typescript
import { describe, expect, it } from "vitest";
import { total } from "../src/total";

function buildBasket(seed: number): number[] {
  const prices: number[] = [];
  prices.push(seed);
  prices.push(seed + 1);
  prices.push(seed + 2);
  prices.push(seed + 3);
  prices.push(seed + 4);
  prices.push(seed + 5);
  prices.push(seed + 6);
  prices.push(seed + 7);
  prices.push(seed + 8);
  prices.push(seed + 9);
  return prices;
}

describe("total", () => {
  it("sums an empty basket to zero", () => {
    expect(total([])).toBe(0);
  });

  it("sums a single price", () => {
    expect(total([12])).toBe(12);
  });

  it("sums a generated basket", () => {
    expect(total(buildBasket(1))).toBe(55);
  });
});
```

```bash
habit-sensors --all | jq -c '[.[0].issues[] | {line: .details.line, message: .details.message}]'
```

🖥️ ✅
```json
[{"line":4,"message":"Function 'buildBasket' has too many lines (14). Maximum allowed is 12."},{"line":19,"message":"Arrow function has too many lines (13). Maximum allowed is 12."}]
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^tests/'
```

🖥️ ❌ 1
```text
── oversized-function (2 issues) ──
tests/basket.test.ts:4
tests/basket.test.ts:19
```

## Wanted

A test-runner callback is a **label**, not a function with a responsibility. Its
length is a statement about how many scenarios share a subject, and shrinking it
does not improve anything — which is precisely why the `oversized-function`
guide has no advice for it. The tool must never trade real test structure for a
counter.

The narrow fix is to stop measuring the callback passed to a test-runner
grouping or case (`describe`, `it`, `test`, `beforeEach`, and their `.each` /
`.only` / `.skip` variants) as a function of its own — either exempt outright,
or given its own far larger threshold on the argument that a group of forty
scenarios really is worth splitting. Either way, the callback body is not
counted into a *parent* callback's total, so nesting stops being what trips it.

What must not change: everything else in a test file. Test code is production
code — a helper, a factory, a fixture builder inside a test file is an ordinary
function and is measured like one. The exemption is for the runner's callback,
not for the directory.

### A describe with three its is not an oversized function 🟡

The file from the first Today case, unchanged. Nothing in it is a smell, so the
run is clean and the agent is never pushed into splitting the group.

📄tests/total.test.ts
```typescript
import { describe, expect, it } from "vitest";
import { total } from "../src/total";

describe("total", () => {
  it("sums an empty basket to zero", () => {
    expect(total([])).toBe(0);
  });

  it("sums a single price", () => {
    expect(total([12])).toBe(12);
  });

  it("sums several prices", () => {
    expect(total([1, 2, 3])).toBe(6);
  });
});
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

### A single well-formed test case is not an oversized function 🟡

One `it`, six assertions, no `describe` — clean, so arrange/act/assert stays
available to an agent writing a test.

📄tests/receipt.test.ts
```typescript
import { expect, it } from "vitest";
import { checkout } from "../src/checkout";

it("charges a loyal customer the discounted total", () => {
  const basket = [
    { sku: "A", price: 10, quantity: 2 },
    { sku: "B", price: 5, quantity: 1 },
  ];
  const receipt = checkout(basket, { loyalty: true });
  expect(receipt.lines).toHaveLength(2);
  expect(receipt.subtotal).toBe(25);
  expect(receipt.discount).toBe(2.5);
  expect(receipt.total).toBe(22.5);
  expect(receipt.currency).toBe("EUR");
  expect(receipt.giftWrapped).toBe(false);
});
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

### A real helper inside a test file is still reported 🟡

The exemption is for the runner's callback, not for the file. `buildBasket` is an
ordinary fourteen-line function that happens to live in a test, and it is still
the finding — now on its own, with no grouping callback beside it to dilute it.

📄tests/basket.test.ts
```typescript
import { describe, expect, it } from "vitest";
import { total } from "../src/total";

function buildBasket(seed: number): number[] {
  const prices: number[] = [];
  prices.push(seed);
  prices.push(seed + 1);
  prices.push(seed + 2);
  prices.push(seed + 3);
  prices.push(seed + 4);
  prices.push(seed + 5);
  prices.push(seed + 6);
  prices.push(seed + 7);
  prices.push(seed + 8);
  prices.push(seed + 9);
  return prices;
}

describe("total", () => {
  it("sums an empty basket to zero", () => {
    expect(total([])).toBe(0);
  });

  it("sums a single price", () => {
    expect(total([12])).toBe(12);
  });

  it("sums a generated basket", () => {
    expect(total(buildBasket(1))).toBe(55);
  });
});
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^tests/'
```

🖥️ ❌ 1
```text
── oversized-function (1 issue) ──
tests/basket.test.ts:4
```
