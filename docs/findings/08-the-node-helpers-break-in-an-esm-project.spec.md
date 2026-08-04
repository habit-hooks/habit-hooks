# 08. The Node helpers break in an ESM project

The typescript plugin ships two helper scripts — `sensors/knip.js` and
`sensors/comment.js` — written as CommonJS and named `.js`. Node does not decide
a `.js` file's module type from the file; it walks up from the script to the
nearest `package.json` and reads `"type"` there. Put either helper anywhere
inside a project that declares `"type": "module"` — the default a new TypeScript
project is scaffolded with — and the first line of each is a syntax-level death:

```text
const { spawnSync } = require("node:child_process");
                      ^
ReferenceError: require is not defined in ES module scope, you can use import instead
```

That is two of the typescript plugin's three sensors gone on the first run, and
the README, the plugin docs and the config reference between them say `ESM`,
`"type": "module"` and `.cjs` exactly zero times. The cold-start study hit it on
adoption and had to rename both helpers to `.cjs` by hand.

**Which installs are inside the project.** The helper is only in the consumer's
`package.json` scope when it lives under the project directory, so:

- **Vendoring** — `.habit-hooks/typescript/sensors/knip.js`, the route the README
  offers for installs that cannot take extras ("Alternatively, vendor a plugin's
  files under `.habit-hooks/<plugin>/`") — always breaks. That is the first case
  below.
- **A project-local Python venv** — `pip`/`uv pip install` into `.venv/` at the
  project root — breaks too: `.venv/lib/pythonX.Y/site-packages/…/knip.js` is
  still under the project's `package.json`. The third case pins that, running the
  byte-identical shipped file from that path.
- `uv tool install` / `uvx` put the package outside the project, so those escape
  today — by luck of layout, not by design.

The Node tools live in `plugins/typescript/node_modules`; the intro symlinks that
into each case as `./node_modules` and puts its `.bin` on `PATH` once. The
vendored sensor files are copied from the plugin package itself, byte for byte —
no case here rewrites them.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript"]

[sensors.eslint]
disabled = true
```

📄.habit-hooks/typescript/sensors/knip.js @plugins/typescript/src/habit_hooks_typescript/sensors/knip.js

📄.habit-hooks/typescript/sensors/knip.toml @plugins/typescript/src/habit_hooks_typescript/sensors/knip.toml

📄.habit-hooks/typescript/sensors/comment.js @plugins/typescript/src/habit_hooks_typescript/sensors/comment.js

📄.habit-hooks/typescript/sensors/comment.toml @plugins/typescript/src/habit_hooks_typescript/sensors/comment.toml

📄knip.json @plugins/typescript/src/habit_hooks_typescript/knip.json

📄src/cli.ts
```typescript
import { used } from "./helper";

used();
```

📄src/helper.ts
```typescript
export function used(): void {
  // this comment restates what the code already says clearly
}

export function neverUsed(): void {}
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## Today

### Both Node sensors die in a project that declares `"type": "module"`

Delete this case when the fix lands.

One line of the consumer's `package.json` decides it. The project has an unused
export and a non-essential comment — the smells the two sensors exist to find —
and neither is reported: both sensors fail, the run comes back incomplete, and
what the project gets instead of coaching is a Node stack trace about a keyword.

📄package.json
```json
{ "name": "demo", "version": "0.0.0", "type": "module" }
```

```bash
habit-sensors --all >out.json 2>err.txt; echo "exit=$?"
jq -c 'map(.smell)' out.json
grep -o "sensor '[a-z]*' failed" err.txt | sort
grep -c "ReferenceError: require is not defined in ES module scope" err.txt
```

🖥️ ✅
```text
exit=1
["incomplete-run"]
sensor 'comment' failed
sensor 'knip' failed
2
```

### The same files, in a CommonJS project, report both smells

**Keep this case when the fix lands** — it is the control. Identical project,
identical vendored helpers, one key removed from `package.json`. Both sensors run
and both smells come out, which is what makes the case above a packaging defect
rather than a broken helper.

📄package.json
```json
{ "name": "demo", "version": "0.0.0" }
```

```bash
habit-sensors --all 2>/dev/null | jq -c '[.[] | {smell, key: .issues[0].key}] | sort_by(.smell)'
```

🖥️ ✅
```text
[{"smell":"non-essential-comment","key":"src/helper.ts"},{"smell":"unused-export","key":"neverUsed"}]
```

### A project-local venv install puts the shipped helper under the consumer's manifest too

Delete this case when the fix lands.

Vendoring is not the only way in. `pip install habit-hooks[typescript]` into a
`.venv/` at the project root lands the package data at
`.venv/lib/pythonX.Y/site-packages/habit_hooks_typescript/sensors/knip.js` —
still inside the project, so Node still reads the project's `"type": "module"`
and still refuses to run it. The file below is the shipped one, copied verbatim
to the path such an install uses; running it needs no habit-hooks at all, which
is the point: nothing about the helper decides this, only where it sits.

📄package.json
```json
{ "name": "demo", "version": "0.0.0", "type": "module" }
```

📄.venv/lib/python3.12/site-packages/habit_hooks_typescript/sensors/knip.js @plugins/typescript/src/habit_hooks_typescript/sensors/knip.js

```bash
node .venv/lib/python3.12/site-packages/habit_hooks_typescript/sensors/knip.js 2>err.txt; echo "exit=$?"
grep -o "ReferenceError: require is not defined in ES module scope" err.txt
```

🖥️ ✅
```text
exit=1
ReferenceError: require is not defined in ES module scope
```

## Wanted

A helper the consumer never edits should not have its module system decided by
the consumer's `package.json`. Two fixes do it, and either is enough: name the
helpers `.cjs`, or ship a `package.json` declaring `{"type": "commonjs"}` next to
them inside the package. `.cjs` is the smaller change — two renames and the two
`command =` lines that spawn them — and it also survives being vendored, where a
sibling `package.json` would have to be vendored too.

Whichever lands, the vendoring route the README documents has to keep working:
copying the plugin's files into `.habit-hooks/<plugin>/` is an advertised install,
not a workaround.

### An ESM project gets both findings out of the box 🟡

The Today fixture, unchanged, with the helpers named `.cjs` as shipped.

📄package.json
```json
{ "name": "demo", "version": "0.0.0", "type": "module" }
```

```bash
habit-sensors --all 2>/dev/null | jq -c '[.[] | {smell, key: .issues[0].key}] | sort_by(.smell)'
```

🖥️ ✅
```text
[{"smell":"non-essential-comment","key":"src/helper.ts"},{"smell":"unused-export","key":"neverUsed"}]
```

### The docs name the hazard 🟡

A consumer who does hit it — an old vendored copy, a helper of their own — should
find the answer where they look, not in a stack trace. One line in the typescript
plugin's docs is enough.

```bash
grep -c "type\": \"module\"" ../../plugins/typescript/docs/typescript-plugin.spec.md
```

🖥️ ✅
```text
1
```
