# 07. An unmapped tool issue blocks the build, uncoached

The knip sensor now forwards **every** knip issue key, not only the six it has a
smell for (`sensors/knip.js`: `SMELL_BY_KEY[row.knipKey] || row.knipKey`). That
is a real improvement — OpenBoard gained 24 genuine findings that 1.0.3 was
silently discarding. The cost arrives with it: a key that has no smell is
forwarded **under knip's own name**, and everything downstream then treats that
name as a smell it has never heard of.

Two defaults compound. `rendering.severity_of` ends in
`DEFAULT_SEVERITY.get(smell, ENFORCED)`, so a smell absent from
`catalogue.py`'s 25-entry catalogue is **enforced** — it fails the run.
`_resolve_guide` finds no `guides/binaries.md` anywhere and falls back to
`uncoached.md` — generic boilerplate that cannot say anything about the actual
rule. Blocking plus uncoached is the worst pairing available: it stops the build
and then declines to explain why.

3dmaze hit it on a repository nobody had touched:

```text
── binaries (1 issue) ──

General guidance: the issues listed are code smells. …

package.json
```

`binaries` is knip reporting that a `package.json` script runs a binary the
manifest does not declare. The binary was `habit-hooks` — a **Python** tool on
`PATH`, and the npm package of the same name is a dead stub 3dmaze deliberately
does not depend on. A correct-by-design setup, a red build, and coaching that
names neither the tool nor the rule.

Of the keys knip 5 actually emits — `dependencies`, `devDependencies`,
`optionalPeerDependencies`, `exports`, `files`, `classMembers`, `types`,
`unlisted`, `unresolved`, `binaries`, `duplicates`, `enumMembers`, `catalog` —
only the first six have a smell. The other seven all land in this state.

The pass-through itself is right; the defaults behind it are not. A key nobody
has written a guide for is, by construction, a key nobody has decided is worth
failing a build over.

## Today

The cases here feed `habit-mapper` directly, which is where the severity and
guide decisions are made; the last one drives the whole pipeline through real
knip so the finding is pinned against the tool, not only against our model of it.

### An unmapped knip key is enforced and uncoached

Delete this case when the fix lands.

The finding is exactly what the knip sensor emits for 3dmaze's `package.json`.
The run fails (exit 1) and the coaching is the one-size boilerplate.

⌨️
```json
[
  {
    "smell": "binaries",
    "language": "typescript",
    "details": {},
    "issues": [
      {
        "key": "habit-hooks",
        "details": { "file": "package.json", "name": "habit-hooks", "source": "knip:binaries" }
      }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── binaries (1 issue) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.

package.json
```

### A mapped knip key coaches from its own guide — keep this case

**Keep this case after the fix.** The discriminator: the same sensor, the same
shape of finding, one key further along the map. `dependencies` has a smell
(`unused-dependency`), so it renders the guide written for it — proving the
Today case above is about the missing mapping, not about knip findings in
general. Whatever severity an unmapped key gets, a mapped one must keep its
guide.

⌨️
```json
[
  {
    "smell": "unused-dependency",
    "language": "typescript",
    "details": {},
    "issues": [
      {
        "key": "left-pad",
        "details": { "file": "package.json", "name": "left-pad", "source": "knip:dependencies" }
      }
    ]
  }
]
```

```bash
habit-mapper | grep -E '^(──|These dependencies)'
```

🖥️ ❌ 1
```text
── unused-dependency (1 issue) ──
These dependencies are declared but unused:
```

### Real knip turns an unchanged repository red

Delete this case when the fix lands.

3dmaze's shape, built from nothing: a `package.json` whose only script runs
`habit-hooks`, a single clean source file, and knip's own config. knip reports
`binaries: habit-hooks` — correctly, by its own rules — and the pipeline turns
that into a failed build with boilerplate coaching.

The Node tools come from the typescript plugin's own `node_modules`, symlinked
in and put on `PATH`, exactly as
[typescript-plugin.spec.md](../../plugins/typescript/docs/typescript-plugin.spec.md)
does. Only the `knip` sensor runs; `[files]` names the source tree so the scope
never walks the symlink.

📄package.json
```json
{
  "name": "demo",
  "version": "0.0.0",
  "scripts": { "check": "habit-hooks --all" }
}
```

📄knip.json
```json
{ "entry": ["src/index.ts"], "project": ["src/**/*.ts"] }
```

📄src/index.ts
```typescript
export const answer = 42;
```

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]
files   = ["src/**/*.ts"]

[sensors.eslint]
disabled = true

[sensors.comment]
disabled = true
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

knip's own answer, unmapped and unremarkable:

```bash
habit-sensors --all | jq -c '[.[] | {smell, key: .issues[0].key, source: .issues[0].details.source}]'
```

🖥️ ✅
```json
[{"smell":"binaries","key":"habit-hooks","source":"knip:binaries"}]
```

The build the consumer sees:

```bash
habit-hooks --all
```

🖥️ ❌ 1
```text
── binaries (1 issue) ──

General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.

package.json
```

## Wanted

Two fixes, and the first is worth having even after the second.

1. **An uncatalogued smell defaults to `suggested`, not `enforced`.** The
   catalogue is the record of what this product has decided is worth failing a
   build over; a name that is not in it has had no such decision made about it.
   Coaching it and staying green surfaces the finding — which is the whole point
   of the pass-through — without turning somebody else's vocabulary into a gate.
   A project that *does* want a given key blocking already has the lever:
   `[smells.binaries] severity = "enforced"`. The invariant is unchanged for
   everything catalogued, `incomplete-run` included, because those all have
   entries.
2. **Guides for the knip keys real projects actually hit** — `types`, `unlisted`,
   `binaries`, `duplicates` at least. Once a key has a guide it has an owner, and
   whoever writes the guide is exactly the person who should decide its severity.
   `tests/test_catalogue_coverage.py` already refuses a catalogued smell with no
   guide; these would enter through that door.

### An uncatalogued smell coaches but does not block 🟡

The same 3dmaze finding. It still renders — the pass-through is the feature — but
the run stays green until somebody decides otherwise.

⌨️
```json
[
  {
    "smell": "binaries",
    "language": "typescript",
    "details": {},
    "issues": [
      {
        "key": "habit-hooks",
        "details": { "file": "package.json", "name": "habit-hooks", "source": "knip:binaries" }
      }
    ]
  }
]
```

```bash
habit-mapper | head -1
```

🖥️ ✅
```text
── binaries (1 issue) ──
```

### A project can still promote an uncatalogued smell to blocking 🟡

Demoting the default must not take the decision away from a project that has
made it. `[smells.<name>] severity` already carries custom smells
([config.md](../config.md), "Custom smells"); it carries this one too.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]

[smells.binaries]
severity = "enforced"
```

⌨️
```json
[
  {
    "smell": "binaries",
    "language": "typescript",
    "details": {},
    "issues": [
      {
        "key": "habit-hooks",
        "details": { "file": "package.json", "name": "habit-hooks", "source": "knip:binaries" }
      }
    ]
  }
]
```

```bash
habit-mapper | head -1
```

🖥️ ❌ 1
```text
── binaries (1 issue) ──
```

### knip's `binaries` key has coaching of its own 🟡

A guide that knows what the rule means: a script runs a command the manifest does
not declare — which is either a missing dependency or, as in 3dmaze, a tool that
legitimately comes from `PATH` and should be told to knip via `ignoreBinaries`.
The boilerplate can say neither.

⌨️
```json
[
  {
    "smell": "binaries",
    "language": "typescript",
    "details": {},
    "issues": [
      {
        "key": "habit-hooks",
        "details": { "file": "package.json", "name": "habit-hooks", "source": "knip:binaries" }
      }
    ]
  }
]
```

```bash
habit-mapper | grep -c 'General guidance'
```

🖥️ ❌ 1
```text
0
```
