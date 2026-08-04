# 11. habit-hooks reports its own requirements as smells

Follow the README to the letter — install the detectors it names, vendor the
plugin files it offers as the extras-free install route — and the first run
reports what you just installed as code smells you must remove:

```text
── unused-dependency (3 issues) ──
package.json:6     ← eslint     the README told you to install it
package.json:7     ← jscpd      the README told you to install it
package.json:9     ← ts-morph   the README told you to install it

── unused-file (2 issues) ──
.habit-hooks/typescript/sensors/comment.cjs   ← the README's vendoring route
.habit-hooks/typescript/sensors/knip.cjs
```

Both are unfixable as reported. Nothing in a consumer's project *can* import
`jscpd` or `ts-morph` — habit-hooks spawns them, out of process, from a Python
sensor knip has never heard of — so the guide's advice ("delete it, or start
using it") cannot be followed at all. And the override files are not dead code:
they are the sensors doing the reporting. The only way to a green run is to
uninstall the tool or to write ignores no document mentions, and both of those
are a new user's first experience of it.

This is the cold-start study's actual sequence: the `.cjs` extension on the
override files is there because the shipped `.js` helpers cannot run in a project
that declares `"type": "module"` (finding 08). The smell does not depend on the
rename — knip reports the tree under either extension — but the tree is there
because the documented route led to it.

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
{
  "name": "demo",
  "version": "0.0.0",
  "type": "module",
  "devDependencies": {
    "eslint": "^10.4.0",
    "jscpd": "^4.2.5",
    "knip": "^5.88.1",
    "ts-morph": "^28.0.0"
  }
}
```

📄.habit-hooks/typescript/sensors/knip.cjs @plugins/typescript/src/habit_hooks_typescript/sensors/knip.js

📄.habit-hooks/typescript/sensors/knip.toml
```toml
command = "node ${dir}/knip.cjs"
```

📄.habit-hooks/typescript/sensors/comment.cjs @plugins/typescript/src/habit_hooks_typescript/sensors/comment.js

📄.habit-hooks/typescript/sensors/comment.toml
```toml
command = "node ${dir}/comment.cjs ${files}"
```

📄src/index.ts
```typescript
export function greet(name: string): string {
  return `hello ${name}`;
}
```

```bash
ln -s ../../plugins/typescript/node_modules node_modules
```

✏️PATH
```text
$PWD/node_modules/.bin:$PATH
```

## Today

### The detectors the README tells you to install are reported as unused dependencies

Delete this case when the fix lands.

`eslint`, `jscpd` and `ts-morph` are in `devDependencies` because the README's
install section puts them there — jscpd for the generic plugin that ships with
core, eslint and ts-morph for the typescript plugin. No source file imports any
of them, and none ever will: habit-hooks spawns them as external processes. knip
sees three dependencies nothing uses and says so. (knip exempts only itself.)

```bash
habit-sensors --all 2>/dev/null | jq -c '[.[] | select(.smell == "unused-dependency") | {smell, keys: ([.issues[].key] | sort), source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-dependency","keys":["eslint","jscpd","ts-morph"],"source":"knip:devDependencies"}]
```

### The override tree the project vendored is reported as unused files

Delete this case when the fix lands.

The README offers vendoring under `.habit-hooks/<plugin>/` as the install route
for anyone who cannot add extras. Those files are executable sensors that
habit-hooks resolves through the override chain — one of them is the very sensor
producing this finding — but nothing in the project imports them, so knip's
default project patterns sweep them up as dead code. Delete them, as instructed,
and the plugin stops working.

```bash
habit-sensors --all 2>/dev/null | jq -c '[.[] | select(.smell == "unused-file") | {smell, keys: ([.issues[].key] | sort), source: .issues[0].details.source}]'
```

🖥️ ✅
```text
[{"smell":"unused-file","keys":[".habit-hooks/typescript/sensors/comment.cjs",".habit-hooks/typescript/sensors/knip.cjs"],"source":"knip:files"}]
```

### The documented install fails the build it was installed to protect

Delete this case when the fix lands.

End to end, through the renderer the user actually reads: five issues, none of
them about their code, and exit 1 — a failing pre-commit hook on a project whose
only sin was following the instructions.

```bash
habit-hooks --all > render.txt; echo "exit=$?"
grep -E "^(── |package\.json|\.habit-hooks)" render.txt
```

🖥️ ✅
```text
exit=1
── unused-file (2 issues) ──
.habit-hooks/typescript/sensors/comment.cjs
.habit-hooks/typescript/sensors/knip.cjs
── unused-dependency (3 issues) ──
package.json:6
package.json:7
package.json:9
```

## Wanted

A tool cannot bill its own installation as technical debt. The shipped defaults
know both lists — the plugin knows which binaries its sensors spawn, and the core
owns `.habit-hooks/` — so both belong in what the plugin hands its detector, not
in a paragraph telling every consumer to write the same ignores by hand.

That stays a default, not a lock: a project that stops using habit-hooks should
get `jscpd` reported as unused again, so the exemption has to live where the
project can see and override it, alongside the other shipped defaults.

### A project that followed the README runs clean 🟡

The Today fixture, unchanged: the detectors installed as documented, the plugin
vendored as documented, one source file with nothing wrong with it.

```bash
habit-sensors --all | jq -c 'map(.smell)'
```

🖥️ ✅
```text
[]
```

### A dependency the project really does not use is still reported 🟡

The exemption covers the tools the sensors spawn, not "every dependency". A
`left-pad` nothing imports still reports, so the rule keeps its teeth.

📄package.json
```json
{
  "name": "demo",
  "version": "0.0.0",
  "type": "module",
  "devDependencies": {
    "eslint": "^10.4.0",
    "jscpd": "^4.2.5",
    "knip": "^5.88.1",
    "left-pad": "^1.3.0",
    "ts-morph": "^28.0.0"
  }
}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key]}]'
```

🖥️ ✅
```text
[{"smell":"unused-dependency","keys":["left-pad"]}]
```

### A dead file next to the override tree is still reported 🟡

Same shape for `unused-file`: `.habit-hooks/**` is exempt, the project's own
orphan is not.

📄src/orphan.ts
```typescript
export function orphanFn(): void {}
```

```bash
habit-sensors --all | jq -c '[.[] | {smell, keys: [.issues[].key]}]'
```

🖥️ ✅
```text
[{"smell":"unused-file","keys":["src/orphan.ts"]}]
```
