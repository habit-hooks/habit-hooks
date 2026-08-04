# 17. The knip sensor ignores the config it ships

The typescript plugin ships `knip.json`: entry and project patterns narrowed to
`src/**`, `tests/**` listed as an unmarked entry so test files are not read as
dead, and the trailing `!` production markers that gate the second
`knip --production` pass. The sensor that runs knip never mentions it:

```text
$ grep -c -- --config plugins/typescript/src/habit_hooks_typescript/sensors/knip.toml
0
$ grep -c -- --config plugins/typescript/src/habit_hooks_typescript/sensors/knip.js
0
$ grep -n spawnSync plugins/typescript/src/habit_hooks_typescript/sensors/knip.js
52:  return spawnSync("knip", ["--reporter", "json", ...extraArgs], {
```

So knip discovers whatever the consumer has, and the shipped file is dead weight.
The idiom for doing it properly is already in the repo — the generic plugin's
jscpd sensor spells it `--config ${dir}/../.jscpd.json` — and the knip sensor has
the same `${dir}` and does not use it.

Two things follow from that one omission. A project with no knip config of its
own is analysed under knip's built-in defaults, whose `project` is the whole tree
rather than `src/**`: everything the plugin tuned simply does not happen, and
files it never meant to analyse are swept in. That is the mechanism behind
finding 11, where the `.habit-hooks/**` override tree — the sensors doing the
reporting — comes back as `unused-file`; those cases stay there, this one pins
the cause.

The second is quieter. `configMarksProduction()` in `knip.js` reads a JSON config
by the same discovery, so whether the gated `--production` pass runs at all is
decided by the consumer's config while the shipped one, the only config in the
picture that *does* carry the markers, is ignored. A project with no knip config
never gets `test-only-dead-code` — the smell whose whole point is that the fix
deletes the test too.

The Node tools live in `plugins/typescript/node_modules`; the intro symlinks that
into each case as `./node_modules` and puts its `.bin` on `PATH` once. Only the
knip sensor runs, so every finding below is knip's.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.eslint]
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

### A project with no knip config of its own is analysed by knip's defaults

Delete this case when the fix lands.

A plain TypeScript project that has just installed habit-hooks: sources under
`src/`, a build helper under `tools/` that nothing imports because nothing is
meant to. The shipped `project` is `src/**/*.ts` and would never have looked
there. knip's default is the whole tree, so `tools/generate.ts` is reported as
dead code the consumer is told to delete.

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

📄tools/generate.ts
```typescript
export function generate(): void {}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-file","keys":["tools/generate.ts"],"source":"knip:files"},{"smell":"unused-export","keys":["neverUsed"],"source":"knip:exports"}]
```

The config that would have prevented it ships inside the plugin, neither sensor
file names it, and dropping that exact file into the project — which is all the
fix has to arrange — leaves only the real finding:

```bash
test -f ../../plugins/typescript/src/habit_hooks_typescript/knip.json && echo "shipped: knip.json"
grep -c -- "--config" ../../plugins/typescript/src/habit_hooks_typescript/sensors/knip.toml || true
grep -c -- "--config" ../../plugins/typescript/src/habit_hooks_typescript/sensors/knip.js || true
cp ../../plugins/typescript/src/habit_hooks_typescript/knip.json knip.json
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key]}]'
```

🖥️ ✅
```text
shipped: knip.json
0
0
[{"smell":"unused-export","keys":["neverUsed"]}]
```

### The gated production pass is decided by a config the plugin does not control

Delete this case when the fix lands.

`testOnly` is exported by production code and imported only by a test. That is
the `test-only-dead-code` case the plugin built the second `--production` pass
for. Without a knip config in the project, `configMarksProduction()` finds no
markers, the second pass never runs, and the run says two other things instead:
the test file itself is dead (knip's defaults never made `tests/**` an entry) and
`testOnly` is a plain `unused-export`, whose coaching says to delete the export
and never mentions the test that is keeping it alive.

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
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-file","keys":["tests/helper.test.ts"],"source":"knip:files"},{"smell":"unused-export","keys":["testOnly"],"source":"knip:exports"}]
```

The markers the gate looks for are in the shipped config, on both `entry` and
`project` as knip requires. Put that file where discovery can see it and the same
tree reports the smell it was supposed to:

```bash
jq -c '{entry: .entry[0], project: .project[0]}' ../../plugins/typescript/src/habit_hooks_typescript/knip.json
cp ../../plugins/typescript/src/habit_hooks_typescript/knip.json knip.json
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
{"entry":"src/cli.ts!","project":"src/**/*.ts!"}
[{"smell":"test-only-dead-code","keys":["testOnly"],"source":"knip:production:exports"}]
```

### A project's own knip config is the one that drives the run

Keep this case when the fix lands — it is the constraint the fix has to respect.

The one thing the current wiring gets right by accident: a project that has a
knip config gets *that* config. This one opts into `classMembers`, which neither
knip's defaults nor the shipped config include, and keeps `project` to `src/**`,
so `tools/generate.ts` is not swept in. The answer below is reachable from no
other config in the picture — defaults report the orphan file and no class
member, the shipped config reports nothing at all — which is what makes it proof
that the project's own file is what ran.

📄knip.json
```json
{
  "entry": ["src/cli.ts"],
  "project": ["src/**/*.ts"],
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

📄tools/generate.ts
```typescript
export function generate(): void {}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-class-member","keys":["unusedMethod"],"source":"knip:classMembers"}]
```

## Wanted

The sensor runs the config the plugin ships, so that config is what the plugin's
knip findings mean and what these specs test. Everything downstream of it follows
from the same change: the patterns are the plugin's, `tests/**` is an entry rather
than dead weight, and the gate on the second pass reads the markers of the config
that is actually in force.

A consumer with their own knip config still wins — a shipped default is a
default, and knip's own discovery is where a project already expects to state
one — but no consumer has to author a config before the plugin analyses the tree
it was tuned for.

### The plugin's own knip config is what runs when the project has none 🟡

The same tree as the Today case, in the same config-less project. The shipped
`project` stops at `src/**`, so the build helper is not the consumer's problem;
the genuinely unused export still is.

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

📄tools/generate.ts
```typescript
export function generate(): void {}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-export","keys":["neverUsed"],"source":"knip:exports"}]
```

### Test-only dead code reports without the project writing a knip config 🟡

The gate reads the shipped markers because the shipped config is what ran. The
test file is an entry, so it is not dead, and `testOnly` comes back as
`test-only-dead-code` — the smell whose guide says to remove the test as well —
rather than as a plain unused export.

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
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"test-only-dead-code","keys":["testOnly"],"source":"knip:production:exports"}]
```

### A project's own knip config still wins, gate included 🟡

The Today keeper's guarantee taken one step further, to the part a fix is most
likely to break: this project's config has no `!` anywhere, so the second pass
must not run — even though the config the plugin ships does carry the markers.
`testOnly` stays silent because the project listed `tests/**` as an entry, and
`neverUsed` still reports, so silence is an answer and not a dead sensor.

📄knip.json
```json
{
  "entry": ["src/cli.ts", "tests/**"],
  "project": ["src/**/*.ts"]
}
```

📄src/helper.ts
```typescript
export function prodUsed(): void {}

export function testOnly(): void {}

export function neverUsed(): void {}
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
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key], source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-export","keys":["neverUsed"],"source":"knip:exports"}]
```
