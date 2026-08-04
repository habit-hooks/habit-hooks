# 01. `--prune` empties an index it was never shown

`habit-snooze --prune` drops every index key the run no longer reports. That is
only safe if the run it reads could have reported them — and the default pipe
cannot, because the snooze transformer already removed exactly those issues
before `--prune` ever sees them. Leave `--no-snooze` off and the index destroys
itself:

```text
$ habit-snooze --list
src/x.js
src/y.js

$ habit-sensors --all | habit-snooze --prune      # note: no --no-snooze
$ echo $?
0
$ habit-snooze --list
$
```

Two keys in, nothing out, exit 0, not a word said. The checked-in baseline is
gone and the next run fails on every smell the team had agreed to defer. A field
study destroyed a 208-key index this way; the toy run above is the same bug at
three keys.

**This is the residual gap of a deliberate fix, not a new discovery.** #94
(`b516ec1`) named this exact pipeline — DECISIONS.md, "`--prune` reads a
snooze-free run, and never empties on nothing", says the documented
`habit-sensors --all | habit-snooze --prune` "kept only the index keys present in
a stream that by construction held none of them, rewriting the whole index to
`[]` with exit 0 — one run silently destroying a team's baseline". It shipped two
answers: `habit-sensors --no-snooze` as the correct seam, and a guard in `_prune`
refusing when the run reports *nothing at all*. The guard asks whether anything
was measured (`if index and not present`), but the invariant it is standing in
for is whether the input was snooze-free. One surviving finding satisfies the
guard and prunes the rest, which is why the field study's index went from 208
keys to 1 rather than to 0. The cases below pin both halves: the guard that works
stays, the hole beside it closes.

The near miss is that habit-hooks already knows this shape. `_prune` refuses when
the run is **wholly** empty (#94) — right diagnosis, wrong trigger. One
un-snoozed finding anywhere in the run is enough to make the pipe non-empty, and
then every snoozed key looks obsolete because the snooze transformer is the thing
that removed it. The guard fires in the rare case and stands aside in the common
one.

The documented pipeline is `habit-sensors --no-snooze | habit-snooze --prune`
([habit-snooze.spec.md](../habit-snooze.spec.md)), and that pipeline is correct.
The finding is that forgetting one flag silently deletes a checked-in file.

Every case below runs the real pipeline through a stub sensor, so the bypass that
hid #94 cannot hide this one either. Discovery is opt-in (#97), so the config
names a scope.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["alpha"]
```

📄.habit-hooks/generic/sensors/alpha.toml
```toml
command = "cat ${dir}/alpha.json"
```

📄src/x.js
```js
export const equal = (a, b) => a == b;
```

📄src/y.js
```js
export const same = (a, b) => a == b;
```

📄src/z.js
```js
export const alike = (a, b) => a == b;
```

## Today

### A snooze-filtered pipe prunes the whole index away

Delete this case when the fix lands.

The sensor reports three keys; two of them are snoozed, so the default pipe hands
`--prune` only the third. `--prune` reads that as "the other two are obsolete"
and writes an empty index — exit 0, nothing on stdout, nothing on stderr.

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"loose-equality","details":{"maxAllowed":0},"issues":[
  {"key":"src/x.js","details":{"file":"src/x.js","line":1}},
  {"key":"src/y.js","details":{"file":"src/y.js","line":1}},
  {"key":"src/z.js","details":{"file":"src/z.js","line":1}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/x.js", "src/y.js"]
```

What `--prune` is about to be handed — one key, because snooze removed the other
two on the way past:

```bash
habit-sensors --all | jq -c '[.[].issues[].key]'
```

🖥️ ✅
```json
["src/z.js"]
```

The prune itself says nothing at all:

```bash
habit-sensors --all | habit-snooze --prune
```

🖥️ ✅
```text
```

And the checked-in index is now empty:

```bash
cat .habit-hooks/snooze.json
```

🖥️ ✅
```json
[]
```

### The wholly-empty run is still refused — keep this case

**Keep this case after the fix.** It pins the #94 guard that already works; a
wider refusal must not regress it into a different message or a different exit
code.

Same pipe, but now every reported key is snoozed, so the pipe drains to `[]`.
That is the one case `_prune` recognises: it refuses, explains itself on stderr,
exits 1, and leaves the index byte for byte as it found it.

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"loose-equality","details":{"maxAllowed":0},"issues":[
  {"key":"src/x.js","details":{"file":"src/x.js","line":1}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/x.js"]
```

```bash
habit-sensors --all | habit-snooze --prune
```

🖥️ ❌ 1

🚨
```text
habit-snooze: --prune read no findings; refusing to empty a populated index. Nothing was measured — feed it a snooze-free run (`habit-sensors --no-snooze | habit-snooze --prune`). Index left unchanged.
```

```bash
cat .habit-hooks/snooze.json
```

🖥️ ✅
```json
["src/x.js"]
```

### The documented pipeline still prunes correctly

**Keep this case after the fix.** Whatever refusal is added must not break the
one invocation that is right: `--no-snooze` shows `--prune` every finding the run
still makes, snoozed or not, so a key that is still violating survives and only a
genuinely obsolete one is reaped.

`src/x.js` is still reported, `src/y.js` is not.

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"loose-equality","details":{"maxAllowed":0},"issues":[
  {"key":"src/x.js","details":{"file":"src/x.js","line":1}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/x.js", "src/y.js"]
```

```bash
habit-sensors --all --no-snooze | habit-snooze --prune && habit-snooze --list
```

🖥️ ✅
```text
src/x.js
```

## Wanted

A user must not be able to delete a checked-in baseline by forgetting a flag.
`--prune` needs to know whether the findings it was handed could contain the
index's keys, and refuse when they could not — the same judgement `_prune`
already makes for the empty run, just made on the right question.

The cheapest signal is already in the pipe's own provenance: a run that kept its
snooze transformers is, by construction, a run with every snoozed key filtered
out of it. `habit-sensors` could stamp that on its output (or `--prune` could
require the stamp), so the refusal is structural rather than a guess.

### `--prune` refuses a run that was snooze-filtered 🟡

The pipe is the destructive one from the first Today case. `--prune` must not
write the index; it must exit non-zero and name the flag that makes the pipeline
correct.

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"loose-equality","details":{"maxAllowed":0},"issues":[
  {"key":"src/x.js","details":{"file":"src/x.js","line":1}},
  {"key":"src/y.js","details":{"file":"src/y.js","line":1}},
  {"key":"src/z.js","details":{"file":"src/z.js","line":1}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/x.js", "src/y.js"]
```

```bash
habit-sensors --all | habit-snooze --prune
```

🖥️ ❌ 1

🚨
```text
habit-snooze: --prune was handed a snooze-filtered run; it cannot see the keys it would drop. Re-run as `habit-sensors --no-snooze | habit-snooze --prune`. Index left unchanged.
```

### The refused prune leaves the index untouched 🟡

Refusing is only half of it: the point of the refusal is that the checked-in file
survives. Same setup as above, asserted on the file rather than the message.

📄.habit-hooks/generic/sensors/alpha.json
```json
[{"smell":"loose-equality","details":{"maxAllowed":0},"issues":[
  {"key":"src/x.js","details":{"file":"src/x.js","line":1}},
  {"key":"src/y.js","details":{"file":"src/y.js","line":1}},
  {"key":"src/z.js","details":{"file":"src/z.js","line":1}}]}]
```

📄.habit-hooks/snooze.json
```json
["src/x.js", "src/y.js"]
```

```bash
habit-sensors --all | habit-snooze --prune || true
```

```bash
cat .habit-hooks/snooze.json
```

🖥️ ✅
```json
["src/x.js", "src/y.js"]
```
