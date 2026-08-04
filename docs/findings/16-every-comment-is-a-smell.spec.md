# 16. Every comment is a smell

`non-essential-comment` applies exactly two tests, and neither is about meaning.
`comment.js` reports a `//` line if it is **ten characters or longer** and does
**not contain `eslint-disable`**. That is the whole rule. In the field study's
toy repo it fired on all 28 `//` comments in the tree — and the 15 lines of
genuinely commented-out code, the ones worth acting on, were 15 entries in a list
of 28 identical-looking entries.

The guide it renders knows better than the sensor does. Its third paragraph says:
"Remove comments unless they impact functionality … or explain *why* something
non-obvious was chosen (a workaround for a specific library bug, a reference to a
spec)." The sensor reports the *why*-comment anyway, so the listing contradicts
the prose above it — and the listing is the part an agent acts on.

That is not theoretical. In the feature-work study the finding drove the agent to
**delete** a comment recording why a new pricing rule lived in its own function
rather than folded into an existing one. Its own verdict on the change was "net
negative… there is now zero explanation in the source for why". The reasoning was
unrecoverable from the code, because a *why* is exactly what code cannot show —
which is why this project's own CLAUDE.md keeps that class of knowledge in
writing ("a gotcha that surprised me earns a short note there too") while
refusing to record design that is "visible in the code: fix the naming instead".
The tool should be enforcing that split. Today it flattens it.

Before, in one file — three different things, one verdict:

```text
── non-essential-comment (5 issues) ──
…
src/pricing.ts:3     ← commented-out code
src/pricing.ts:4     ← commented-out code
src/pricing.ts:7     ← the constraint that must survive
src/pricing.ts:8     ← …continued, counted twice
src/pricing.ts:10    ← a redundant restatement of the next line
```

These cases run the real `comment` sensor, because the finding is about what
ts-morph and that sensor actually classify. The Node tools come from the
typescript plugin's `node_modules`, symlinked in and put on `PATH` as
[typescript-plugin.spec.md](../../plugins/typescript/docs/typescript-plugin.spec.md)
does. Every other sensor is off so the comment sensor is the only voice.

📄package.json
```json
{ "name": "demo", "version": "0.0.0" }
```

📄.habit-hooks/config.toml
```toml
plugins = ["typescript", "generic"]

[sensors.eslint]
disabled = true

[sensors.knip]
disabled = true

[sensors.jscpd]
disabled = true

[sensors.line-count]
disabled = true
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

📄src/pricing.ts
```typescript
const BONUS_RATE = 0.05;

// export function priceWithLegacyTax(order: Order): number {
//   return order.net * 1.19;
// }

// Kept out of priceOrder deliberately: the tax authority audits this rule on
// its own, and folding it in makes the audited path unreadable in a diff.
export function priceLoyaltyBonus(net: number): number {
  // multiply the net by the bonus rate
  return net * BONUS_RATE;
}
```

## Today

### Dead code, a constraint and a restatement all report identically

Delete this case when the fix lands.

One file, three kinds of comment. Lines 3–5 are commented-out code. Lines 7–8
record a constraint the code cannot express — the reason this function is
separate. Line 10 restates the line below it in English. All three arrive under
one banner as bare `file:line`, in source order, with nothing to rank or
distinguish them.

The two-line constraint is also counted **twice**, once per physical line, so the
one comment that should not be there at all is the largest contributor to the
count. Meanwhile line 5 — the closing `// }` of the commented-out function — is
four characters long and falls under the sensor's ten-character floor, so even
the dead code is reported incompletely.

```bash
habit-sensors --all | jq -c '[.[0].issues[] | .details.line]'
```

🖥️ ✅
```json
[3,4,7,8,10]
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ✅
```text
── non-essential-comment (5 issues) ──

Comments indicate code that is not self-documenting. The smell is the *need* for the comment — the reader could not work out what the code does from the names and structure alone.

Extract complex logic into well-named functions instead of explaining with a comment. A function called `applyDiscountForLoyalCustomers` does not need a header explaining what it does.

Remove comments unless they impact functionality (executable annotations) or explain *why* something non-obvious was chosen (a workaround for a specific library bug, a reference to a spec). Comments that explain *what* the code does are almost always redundant — or worse, drift out of sync with the code and start lying.

Do not delete an `eslint-disable` or shebang on autopilot — those are flagged separately and exempted from this rule.

src/pricing.ts:3
src/pricing.ts:4
src/pricing.ts:7
src/pricing.ts:8
src/pricing.ts:10
```

### The commented-out block that mattered is buried mid-list

Delete this case when the fix lands.

Same file, reduced to what the agent scans first. The dead code is at positions
one and two of five, indistinguishable from the two entries that must survive and
the one that is merely redundant. Scale that to the study's toy repo — 15
commented-out lines inside 28 identical entries — and the signal is gone.

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ✅
```text
── non-essential-comment (5 issues) ──
src/pricing.ts:3
src/pricing.ts:4
src/pricing.ts:7
src/pricing.ts:8
src/pricing.ts:10
```

### The only tests the sensor applies are length and a substring

Delete this case when the fix lands.

Three comments, three different fates, and meaning decides none of them. `// n/a`
is silent because it is six characters. The `eslint-disable` line is silent
because of a substring match. The one that cites a finance spec — the textbook
case the guide says to keep — is the only one reported.

The exemption list proves the mechanism already exists: the sensor can carve out
a class of comment. It just carves out the wrong one.

📄src/filter.ts
```typescript
// n/a
// eslint-disable-next-line no-console
export function debugTotal(net: number): number {
  // VAT is charged on the gross, never the net — see finance spec section 4.2.
  return net;
}
```

📄src/pricing.ts
```typescript
const BONUS_RATE = 0.05;

export function priceLoyaltyBonus(net: number): number {
  return net * BONUS_RATE;
}
```

```bash
habit-sensors --all | jq -c '[.[0].issues[] | {line: .details.line, message: .details.message}]'
```

🖥️ ✅
```json
[{"line":4,"message":"single-line comment: \"// VAT is charged on the gross, never the net — se...\""}]
```

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ✅
```text
── non-essential-comment (1 issue) ──
src/filter.ts:4
```

## Wanted

Three changes, and none of them shortens the coaching — the long-form prose is
what teaches the distinction, so it gets *longer*, not shorter.

**Commented-out code becomes its own smell.** `commented-out-code`, enforced, a
new key in [smell-vocabulary.md](../smell-vocabulary.md) with its own guide: this
is dead code, version control remembers it, delete it. It is a different problem
with a different fix from "this comment explains what the code already says", and
it is the one an agent should clear first. Contiguous commented-out lines are one
issue with a line range, so a ten-line commented-out function costs one entry,
not ten.

**A constraint comment is not reported at all.** A comment that states something
the code cannot show — an external rule, an audit boundary, a spec reference, a
library bug — is the one kind worth keeping, and the guide already says so. A
sensor that reports it while the guide says to keep it teaches an agent to
distrust both. The classification does not have to be perfect to beat reporting
everything; the cost of a missed *what*-comment is one redundant line, and the
cost of a reported *why*-comment is a design decision deleted from the source.

**The guide teaches the split.** With three outcomes instead of one, the prose
has to name which is which, so an agent that reads it once carries the rule into
code it writes later. That is the whole point of long-form coaching, and it is
wasted on a listing that makes no distinction to explain.

### Commented-out code is its own smell 🟡

The pricing file again. The commented-out block is one enforced finding with a
line range; the redundant restatement stays a suggestion; the constraint is
gone from the report entirely.

```bash
habit-sensors --all | habit-mapper | grep -E '^──|^src/'
```

🖥️ ❌ 1
```text
── commented-out-code (1 issue) ──
src/pricing.ts:3-5
── non-essential-comment (1 issue) ──
src/pricing.ts:10
```

### A constraint comment is left alone 🟡

The file whose only comment cites the finance spec. There is nothing to coach, so
the run is clean and the agent has no reason to delete the one line that records
why the code is the way it is.

📄src/filter.ts
```typescript
// n/a
// eslint-disable-next-line no-console
export function debugTotal(net: number): number {
  // VAT is charged on the gross, never the net — see finance spec section 4.2.
  return net;
}
```

📄src/pricing.ts
```typescript
const BONUS_RATE = 0.05;

export function priceLoyaltyBonus(net: number): number {
  return net * BONUS_RATE;
}
```

```bash
habit-sensors --all | habit-mapper
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

### The guide names the comment worth keeping 🟡

The distinction has to reach the agent as a rule it can apply next time, not just
as a filter it never sees. The `non-essential-comment` guide states it outright.

```bash
habit-sensors --all | habit-mapper | grep -c 'A comment that states a constraint the code cannot show is the one kind worth keeping'
```

🖥️ ✅
```text
1
```

### The commented-out guide says to delete, not to tidy 🟡

The new smell needs its own advice, and it is not the advice
`non-essential-comment` gives. Extracting a well-named function does nothing for
a block that is already switched off.

```bash
habit-sensors --all | habit-mapper | grep -c 'Delete it. Version control remembers the code you switched off'
```

🖥️ ✅
```text
1
```
