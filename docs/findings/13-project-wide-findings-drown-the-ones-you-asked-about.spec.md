# 13. Project-wide findings drown the ones you asked about

Two of the shipped sensors take no file list at all. `knip.toml` is
`node ${dir}/knip.js` and `jscpd.toml` is `${python} ${dir}/jscpd.py --config …`
— neither mentions `${files}`, so neither can be scoped. Every run of
`habit-hooks --file one.ts` therefore re-reports the whole project's unused
exports, unused files, unused dependencies and duplicated blocks, mixed in among
the findings that really are about `one.ts`, with nothing in the render saying
which is which.

A field study ran the gate on five single files during a real feature change.
The whole-project block was byte-identical in all five runs — 13 findings the
agent had already read, re-rendered every time — and the five checks emitted
37.9KB in total. The agent's verdict was that the noise "actively worked against
the one thing the gate exists to catch": it fixed all three findings its own code
introduced, but reported that it stopped reading the coaching prose after the
first repetition.

That last part is the trap. The long-form coaching is the product's edge and the
same agent insisted it must **not** be shortened. The fix is not less prose —
it is not printing the same prose twice, and telling the agent which findings it
just caused:

```text
── oversized-function (1 issue) ──          ← yours
… 6 paragraphs of coaching …
src/edited.js:1

── unused-export (2 issues) ──              ← the project's, unchanged for months
… 5 paragraphs of coaching …
src/untouched.js
src/orphan.js
```

Both blocks look equally urgent, and the second one arrives again on the next
edit, and the one after that.

The cases below use a fixture sensor pair rather than knip and jscpd: `scoped`
echoes back exactly the files it was handed, `project-wide` ignores `${files}`
and reads a fixed report — which is what a sensor whose command has no `${files}`
does. Nothing here depends on knip's or jscpd's own output, so the finding is
pinned deterministically.

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
files   = ["src/**"]
```

📄.habit-hooks/generic/config.toml
```toml
sensors = ["scoped", "project-wide"]
```

📄.habit-hooks/generic/sensors/scoped.toml
```toml
command = "jq -n --args '[{smell: \"oversized-function\", details: {}, issues: ($ARGS.positional | map({key: (. + \":1\"), details: {file: ., line: 1}}))}]' ${files}"
```

📄.habit-hooks/generic/sensors/project-wide.toml
```toml
command = "cat ${dir}/project-wide.json"
```

📄.habit-hooks/generic/sensors/project-wide.json
```json
[{"smell":"unused-export","details":{},"issues":[
  {"key":"src/untouched.js","details":{"file":"src/untouched.js"}},
  {"key":"src/orphan.js","details":{"file":"src/orphan.js"}}]}]
```

The two guides are shortened here on purpose: these cases are about *where* the
render puts the blocks, not about what the shipped prose says. The repetition
case further down uses the real shipped guide, because there the length is the
whole point.

📄.habit-hooks/generic/guides/oversized-function.md
```markdown
Split each function along a real responsibility boundary.

{% include "includes/line_level_issues.md" %}
```

📄.habit-hooks/generic/guides/unused-export.md
```markdown
Delete the export, or wire it to a real entry point.

{% include "includes/file_level_issues.md" %}
```

📄src/edited.js
```js
export const edited = 1;
```

📄src/other.js
```js
export const other = 2;
```

📄src/untouched.js
```js
export const untouched = 3;
```

📄src/orphan.js
```js
export const orphan = 4;
```

## Today

### A `--file` run reports files it was never handed

Delete this case when the fix lands.

`--file src/edited.js` narrows `${files}` to one path, and the scoped sensor
honours it. The project-wide sensor never sees the scope, so its two findings
about files the run did not ask about travel all the way to the agent.

```bash
habit-sensors --file src/edited.js | jq -c '[.[] | {smell, keys: [.issues[].key]}]'
```

🖥️ ✅
```json
[{"smell":"oversized-function","keys":["src/edited.js:1"]},{"smell":"unused-export","keys":["src/untouched.js","src/orphan.js"]}]
```

### Two different `--file` runs return the same project-wide block

Delete this case when the fix lands.

This is the diff the field study ran five times. Whichever file you name, the
project-wide part of the answer is identical — so an agent editing five files in
one task reads the same block five times.

```bash
habit-sensors --file src/edited.js | jq -c '[.[] | select(.smell == "unused-export") | .issues[].key]' > first.json
```

```bash
habit-sensors --file src/other.js | jq -c '[.[] | select(.smell == "unused-export") | .issues[].key]' > second.json
```

```bash
diff first.json second.json && cat first.json
```

🖥️ ✅
```json
["src/untouched.js","src/orphan.js"]
```

### Nothing in the render separates your finding from the project's

Delete this case when the fix lands.

Rendered, the two blocks are the same shape: same banner grammar, same issue
count, same listing. An agent that asked about `src/edited.js` has no way to tell
that the second block is a standing backlog item it did not cause and cannot be
expected to clear as part of this edit.

```bash
habit-sensors --file src/edited.js | habit-mapper
```

🖥️ ❌ 1
```text
── oversized-function (1 issue) ──

Split each function along a real responsibility boundary.

src/edited.js:1

── unused-export (2 issues) ──

Delete the export, or wire it to a real entry point.

src/untouched.js
src/orphan.js
```

### One smell reported twice renders its whole guide twice

Delete this case when the fix lands.

The mapper renders per **finding**, not per smell (`mapper.py`'s
`[render_finding(f, …) for f in findings]`), so a smell that arrives as two
findings prints its guide twice. That is not a corner case: the jscpd sensor
emits **one finding per clone pair** (`clone_finding` in `jscpd.py`), so a file
duplicated into two others produces two `duplicated-code` findings — and the
shipped guide, six paragraphs of it, is re-rendered for the second one with not a
word changed.

This case feeds the mapper jscpd's exact output shape and counts how many times
the guide's opening sentence reaches stdout.

⌨️
```json
[
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/b.js","details":{"file":"src/b.js","startLine":7,"endLine":16}}]},
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/c.js","details":{"file":"src/c.js","startLine":2,"endLine":11}}]}
]
```

```bash
habit-mapper | grep -c 'Duplicated blocks are the cheapest visible sign'
```

🖥️ ✅
```text
2
```

### The repeated guide dwarfs the locations it is repeated for

Delete this case when the fix lands.

Same input, now stripped down to the banners and the locations. Three distinct
duplicated blocks are named across two banners; everything else on stdout is the
same guide, twice. Rendering the first finding alone is 1485 bytes and rendering
both is 2971 — so the second banner spends 1486 bytes to deliver two new lines.

⌨️
```json
[
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/b.js","details":{"file":"src/b.js","startLine":7,"endLine":16}}]},
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/c.js","details":{"file":"src/c.js","startLine":2,"endLine":11}}]}
]
```

```bash
habit-mapper | grep -E '^──|^src/'
```

🖥️ ✅
```text
── duplicated-code (2 issues) ──
src/a.js:3-12
src/b.js:7-16
── duplicated-code (2 issues) ──
src/a.js:3-12
src/c.js:2-11
```

## Wanted

Two changes, neither of which shortens a word of coaching.

**Label each finding by scope reach.** The runner already knows which sensors it
handed a file list to — `${files}` appears in the command or it does not — so it
can stamp every finding with the reach of the sensor that produced it. The
banner then says so, and an agent reading top-down knows in one glance which
findings its own edit caused. Existing banners keep their grammar; only findings
from an unscoped sensor gain the marker, so a `--all` run reads exactly as it
does today.

**Render a smell's guide once per run.** The listing repeats; the prose does not.
Findings of the same smell merge into one banner whose listing carries every
occurrence, so two clone pairs cost two extra lines instead of 1400 extra bytes.
This is the change the field study's agent was really asking for: it stopped
reading after the first repetition precisely because the second copy carried no
new information.

### The banner names a finding's scope reach 🟡

The scoped sensor's finding is about the file the run asked for; the project-wide
sensor's is not, and the render says which is which.

```bash
habit-sensors --file src/edited.js | habit-mapper
```

🖥️ ❌ 1
```text
── oversized-function (1 issue, in scope) ──

Split each function along a real responsibility boundary.

src/edited.js:1

── unused-export (2 issues, project-wide) ──

Delete the export, or wire it to a real entry point.

src/untouched.js
src/orphan.js
```

### An `--all` run is unchanged, because every finding is in scope 🟡

The marker must not become permanent decoration. When the scope is the whole
project there is no distinction left to draw, so the banner stays exactly as it
reads today.

```bash
habit-sensors --all | habit-mapper
```

🖥️ ❌ 1
```text
── oversized-function (4 issues) ──

Split each function along a real responsibility boundary.

src/edited.js:1
src/orphan.js:1
src/other.js:1
src/untouched.js:1

── unused-export (2 issues) ──

Delete the export, or wire it to a real entry point.

src/untouched.js
src/orphan.js
```

### A smell renders its guide once, however many findings carry it 🟡

Two `duplicated-code` findings, one banner, one copy of the guide, every
occurrence still listed. Nothing an agent needs is lost; the second copy of the
prose is.

⌨️
```json
[
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/b.js","details":{"file":"src/b.js","startLine":7,"endLine":16}}]},
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/c.js","details":{"file":"src/c.js","startLine":2,"endLine":11}}]}
]
```

```bash
habit-mapper | grep -c 'Duplicated blocks are the cheapest visible sign'
```

🖥️ ✅
```text
1
```

### The merged banner still lists every occurrence 🟡

Merging must not lose a location. One banner counts all four issues and the
listing names all three distinct blocks.

⌨️
```json
[
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/b.js","details":{"file":"src/b.js","startLine":7,"endLine":16}}]},
  {"smell":"duplicated-code","details":{"lines":9,"tokens":61},
   "issues":[{"key":"src/a.js","details":{"file":"src/a.js","startLine":3,"endLine":12}},
             {"key":"src/c.js","details":{"file":"src/c.js","startLine":2,"endLine":11}}]}
]
```

```bash
habit-mapper | grep -E '^──|^src/'
```

🖥️ ✅
```text
── duplicated-code (4 issues) ──
src/a.js:3-12
src/b.js:7-16
src/a.js:3-12
src/c.js:2-11
```
