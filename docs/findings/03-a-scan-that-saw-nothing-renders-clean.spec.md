# 03. A scan that saw nothing renders clean

`✅ Habit Hooks: automated checks passed.` is the same sentence whether the run
examined four hundred files or none. Nothing in the output distinguishes
*checked and clean* from *never looked*, and both exit 0 — so the agent reading
it, and the human reading the agent, are told the change is fine on the strength
of a scan that never happened.

The everyday way to hit it is trunk-based development. Commit straight onto
`main`, which is also `[scope] branchBase`, and the merge base of `main` and
`HEAD` **is** `HEAD`: the branch changed nothing relative to itself, so the scope
is empty.

```text
$ git log --oneline
575d787 (HEAD -> main) baseline

$ habit-hooks --all
── loose-equality (1 issue) ──
src/x.js:1

$ habit-hooks --branch
✅ Habit Hooks: automated checks passed.
$ echo $?
0
```

Same repository, same smell, one second apart. The second answer is not wrong
about the files it scanned — it scanned none — it is wrong about what it implies.

The same silence appears one level down: a sensor whose own `files` narrows the
run's scope to nothing is skipped (`Execution.run_sensors`, #93 — correct, a tool
handed no paths would otherwise scan the whole repo), and skipping it produces no
finding *and* no notice. Configure the smell detector for `**/*.py` in a
JavaScript project and every run is clean forever.

habit-hooks does have the machinery for this: `scope_notices.py` exists precisely
because "silence about a run that measured nothing is indistinguishable from a
clean one". But it speaks only when `[files]` is unconfigured. Once a project has
named its source — the normal, correct state — an empty scope says nothing at
all.

**This gap is what three earlier efforts left behind, not a fresh discovery.**
#81 (`91483bf`) is committed as "filter git-derived scopes, and never scan
nothing quietly"; #93 (`bea49e1`) made an empty scope run no sensor; #97
(`2dde989`) made discovery opt-in and added the missing-`[files]` notice. Each is
correct and none covers this case, because they all answer "the project has not
told us what to scan" while the failure here is "the project told us, and this
mode legitimately found none of it". The whole condition lives in one line —
`empty_scope_notices` returns `[NO_FILES_NOTICE] if config.files is None else
[]`, so a configured project with an empty git-derived scope takes the `else`
and says nothing. The fix is to report what a run measured, rather than to
explain only the one way a scope can be empty.

Every case below shares one plugin: a sensor that flags each file it is handed,
so a non-empty scope is always visible as a finding and an empty one always
renders the pass message. Discovery is opt-in (#97), so the config names a scope.

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
command = "jq -n --args '[{smell: \"loose-equality\", details: {maxAllowed: 0}, issues: ($ARGS.positional | map({key: ., details: {file: ., line: 1}}))}]' ${files}"
```

📄.habit-hooks/generic/guides/loose-equality.md
```markdown
Use === instead of ==:

{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }}
{% endfor %}
```

📄.habit-hooks/generic/guides/clean.md
```markdown
✅ Habit Hooks: automated checks passed.
```

📄src/x.js
```js
export const equal = (a, b) => a == b;
```

## Today

### Committing straight onto `main` scans nothing and prints the pass message

Delete this case when the fix lands.

`GIT_CEILING_DIRECTORIES` stops git's upward walk at the case directory, so this
case can only ever see the repository it built (CLAUDE.md — a git-backed case
without it is answered about habit-hooks itself).

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add -A &&
  git commit -q -m baseline &&
  git status --porcelain
```

The file is there and it smells — `--all` proves it:

```bash
habit-hooks --all
```

🖥️ ❌ 1
```text
── loose-equality (1 issue) ──

Use === instead of ==:

src/x.js:1
```

`--branch` measures from the merge base of `main` and `HEAD`, which on `main`
with everything committed is `HEAD` itself. Zero files in scope, and the answer
is a pass:

```bash
habit-hooks --branch
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.
```

Nor is anything said on the side channel — `habit-sensors` writes not one line to
stderr about having measured nothing:

```bash
habit-sensors --branch 2>&1 >/dev/null | wc -l | tr -d ' '
```

🖥️ ✅
```text
0
```

### A sensor narrowed to no files contributes no finding and no notice

Delete this case when the fix lands.

The run's scope is not empty here — `src/x.js` is in it — but the sensor's own
`files` keeps only Python, so it is skipped. The findings array comes back empty,
stderr is empty, and the pipeline renders the pass guide: a project can have
every one of its sensors mis-scoped and never learn that nothing runs.

📄.habit-hooks/generic/sensors/alpha.toml
```toml
files   = ["**/*.py"]
command = "jq -n --args '[{smell: \"loose-equality\", details: {maxAllowed: 0}, issues: ($ARGS.positional | map({key: ., details: {file: ., line: 1}}))}]' ${files}"
```

```bash
habit-sensors --all
```

🖥️ ✅
```json
[]
```

```bash
habit-sensors --all 2>&1 >/dev/null | wc -l | tr -d ' '
```

🖥️ ✅
```text
0
```

```bash
habit-hooks --all
```

🖥️ ✅
```text
✅ Habit Hooks: automated checks passed.
```

## Wanted

A pass has to carry its own evidence. "I scanned N files and found nothing" and
"I scanned nothing" are different claims and must read differently — the reader
is a coding agent about to declare the change done.

Failing an empty scope would be wrong: committing on `main` with nothing to
compare is a legitimate "nothing to check", and a pre-commit hook that fails
there is a hook people disable. The fix is to say so, not to break.

The scope layer already knows the count; `scope_notices.py` is where the wording
lives and where it stops short. What is missing is that it only speaks when
`[files]` is unset.

### A clean run states how many files it scanned 🟡

The count belongs in the pass message itself, because that is the line a reader
actually sees.

```bash
habit-hooks --all
```

🖥️ ✅
```text
✅ Habit Hooks: 1 file scanned, no smells found.
```

### A scope of zero files says so instead of passing 🟡

Same repository as the Today case: everything committed on `main`, nothing to
compare. The run still exits 0 — there is nothing wrong with the code — but it
never claims to have checked it.

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

```bash
git init -q -b main . &&
  git config user.email spec@example.com &&
  git config user.name "Spec Runner" &&
  git config commit.gpgsign false &&
  git add -A &&
  git commit -q -m baseline
```

```bash
habit-hooks --branch
```

🖥️ ✅
```text
ℹ️ Habit Hooks: 0 files in scope — nothing was checked. This is not a clean result.
```

### A sensor that examined no files says so on stderr 🟡

The runner skips a sensor whose scope narrowed to nothing (#93). The skip is
right; the silence is not. One line per skipped sensor, on stderr, where the
run's other notices already go — so a project whose sensors are all mis-scoped
finds out on the first run instead of after a quarter of green.

📄.habit-hooks/generic/sensors/alpha.toml
```toml
files   = ["**/*.py"]
command = "jq -n --args '[{smell: \"loose-equality\", details: {maxAllowed: 0}, issues: ($ARGS.positional | map({key: ., details: {file: ., line: 1}}))}]' ${files}"
```

```bash
habit-sensors --all 2>&1 >/dev/null
```

🖥️ ✅
```text
habit-sensors: sensor 'alpha' examined no files — its [sensors.alpha] files kept none of the 1 file in scope
```
