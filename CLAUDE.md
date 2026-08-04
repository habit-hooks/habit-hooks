# habit-hooks notes

## Architecture

### Plugins are installed packages discovered via entry points (human-requested by Ivett)

The core finds plugins through the `habit_hooks.plugins` entry-point group, NOT
by walking a sibling `plugins/` directory. Each plugin is a separately
installable dist `habit-hooks-<name>` whose import package `habit_hooks_<name>`
ships its `config.toml`/`sensors/`/`guides/`/helper scripts/phar as package data
(importlib.resources-accessible). `resolve.installed_plugin_dirs()` maps plugin
name -> package-data dir via `importlib.metadata.entry_points` +
`importlib.resources.files`. The override chain is
`.habit-hooks/<plugin>/<file>` (project) -> `<plugin package data>/<file>`
(default). A configured plugin that is neither overridden under `.habit-hooks/`
nor installed raises a clear error naming `pip install habit-hooks-<name>`
(`Resolver.require_plugin`) — that is the bug-1 root-cause guard.

The repo is a uv workspace (`[tool.uv.workspace] members = ["plugins/*"]`); the
four in-repo plugins live under `plugins/<name>/src/habit_hooks_<name>/` and are
installed editable by `uv sync` for dev. Keeping them in-repo is only a dev
convenience — they do not need to live here. `tests/test_installed_wheel_smoke.py`
builds + installs the core + generic wheels into a throwaway venv and asserts a
real finding comes out; it is the gate that catches "installed runs can't locate
plugins". `${dir}` in a sensor command resolves to the plugin's package-data dir,
so helper-script paths (`${dir}/line-count.py`, `${dir}/../.jscpd.json`) keep
working once the layout is preserved under the import package.

### Sensor `args` live in the sensor's own toml, not the plugin `config.toml` (agent decision)

A sensor's default CLI args (e.g. line-count's `--max 200`) live as `args = [...]`
in `sensors/<name>.toml` and expand into the command via `${args}`. They cannot go
in the plugin `config.toml` because `sensors = [...]` (the ordered list) and a
`[sensors.<name>]` table collide as the same TOML key. A project replaces them
wholesale via `.habit-hooks/config.toml` `[sensors.<name>] args = [...]`
(replace-on-override — `SensorOverride.args`, threaded in `sensors._sensor_args`).

### Finding paths are anchored at the sensor boundary, never per sensor (agent decision, issue #79)

`Execution.run_sensor` pipes every parsed sensor's findings through
`sensors/finding_paths.anchored()`, which re-expresses each `issue.details.file`
**and** `issue.key` relative to the project (`project_paths.project_relative`,
shared with `changed_files.py`). Anchoring the key needs no carve-out: a key
that is not a path (`deptry` keys by module, `knip` by export name) has nothing
to resolve and comes back unchanged. Do not tie the key rewrite to "the key
equals the file" — that leaves `./src/a.py` un-anchored and splits one sensor
key into two spellings, which hides aliasing. Do not add anchoring to a sensor
either: the point is that a third-party sensor obeys a convention it never heard
of, so a snooze index stays portable between a checkout and CI
(`ruff`/`eslint`/`ts-morph` all report absolute paths). Anchoring is **lexical**
— no existence check, because a sensor may report a path the scope never handed
it (a tool's cache, its own scan root), so a key matching none of its files
cannot be caught here. (Deleted paths are no longer a reason: since #81 the
scope drops them before any sensor runs.)
Failures: unanchorable path, or output the contract has no shape for (a
non-object `details`, a non-list `issues`) → `SensorError` (notice, failed run,
that sensor's findings dropped); a key that is one of its own files while
covering others → notice + failed run with the findings kept.

### The scope is narrowed once, in `resolve_scope`, for every mode (agent decision, issue #81)

`resolve_scope` = pick the mode's paths, then narrow them: drop what the work
tree no longer has, then keep only what `[files]` matches (`scope._source_files`).
Do not push either guard into a sensor — every sensor in every plugin, including
third-party ones, would have to re-implement it, and #81 is exactly what happens
when they don't (`line-count.py` reading a deleted path → `FileNotFoundError`,
exit 1, empty stdout, read as clean). `--file` is narrowed too: one setting
answers "what is source here", or it answers nothing.

Git modes measure from the **merge base** of the base ref and `HEAD`, matching
`changed_files.py` — the same question, one answer, so `[scope] branchBase` means
the same thing in a scoped run and in a lapsing snooze. A ref a real repository
cannot resolve is a `SystemExit` naming the ref and whatever chose it (via
`rev-parse --verify --quiet <ref>^{commit}`, as in `changed_files`); "not a git
repository" is checked first and outranks it. Empty output from git is never
allowed to mean "nothing to scan".

Every git mode then widens its history with the **uncommitted work in progress**
(`git_history.uncommitted_changes`, folded in by `scope._with_work_in_progress`,
issue #92): `git diff` never names an untracked path and, commit-to-commit, never
names a staged one, so the file just written — the one most likely to carry a
fresh smell — is exactly the file a diff-built scope would miss. The union is
staged (`git diff --cached`) + unstaged (`git diff`) + untracked non-ignored
(`git ls-files --others --exclude-standard`), each carrying the same `-z` /
`--literal-pathspecs` guards the batched diff needs, then narrowed by
`_source_files` like anything else. This is deliberately **not** shared with
`changed_files.py`: an untracked file's snooze rightly holds (which files to scan
is a different question from which snoozes lapse), so the widening lives in
`scope`, not `git_history`'s shared merge-base question.

`config.load_config` merges the active plugins' declared `files` (union, in
`plugins` order, deduped) when the project names none; the project's own list
replaces them wholesale. That is why `config.py` imports `Resolver` — the merge
needs the override chain, and only `files` has a plugin-supplied default.

### A run that did not complete never renders as clean — including an empty pipe (agent decision, issues #88, #103)

`incomplete-run` is a reserved smell, and `catalogue.incomplete_run_finding`
builds the finding **both** stages raise: `sensors._emit_findings` when
`Run.failed` (after every transformer, so a snooze cannot mute it), and
`mapper.coach_incomplete_run` when stdin is wholly empty. Keep the builder in
`catalogue.py` — the mapper must not import the sensors stage to construct one
finding.

The empty-pipe half exists because the sensors stage can die *before* its
`stdout.write`: a `ToolError` (missing plugin, rejected config, unresolvable
ref) writes zero bytes, and `read_findings` used to map that to `[]` → the ✅.
It now returns `None` for an empty stream, distinct from the `[]` of a completed
empty run — a sound signal only because a completed stage always writes at least
`[]`. Do not "fix" this in `hooks.py` alone: the pipeline exit code was already
right, and the exit code is not what a consuming agent reads — the ✅ line is.

Two deliberate asymmetries: the empty-pipe path exits **2** (`EXIT_TOOL_ERROR`,
the tool broke) where a sensors-raised `incomplete-run` exits 1 (an enforced
finding), and it renders **directly** rather than through `mapper.run`, so
`[smells.incomplete-run] disabled` cannot turn a scan that never ran into a
clean one.

Spec cases that assert the clean guide must feed `[]` explicitly (`⌨️`). A case
with no `⌨️` block inherits pytest's empty stdin, which is now the incomplete
run — that is exactly how the bug hid in `habit-mapper.spec.md`.

### Rendering a finding is `rendering.py`; running the stage is `mapper.py` (agent decision)

`rendering.py` turns **one** finding into text — guide resolution, severity, the
Jinja2 and fix-runner paths, `banner`/`block`. `mapper.py` is the stage around
it: stdin, block order, stderr, exit code. The dependency runs one way
(`mapper` → `rendering`) and must stay that way — the split exists because the
empty-pipe path needs `render_finding` too, and any module that both renders and
owns the entry point ends up importing itself. Both files are also kept under
the repo's own 200-line `oversized-file` gate by it, which the dogfood step
(`uv run habit-hooks --all`) enforces on every CI run.

`rendering.block(finding, text)` is the single source for a printed block
(`── smell (n issues) ──`, blank line, guide text). Format it anywhere else and
a run's output drifts from a coached incomplete run's.

### jscpd resolves a config's relative `path` against the config file, not cwd (agent decision)

When `jscpd --config <abs path>` loads `.jscpd.json`, its `path: ["src"]` resolves
relative to the config file's directory, so a plugin-shipped config scans nothing
in the consumer repo. `plugins/generic/sensors/jscpd.py` therefore reads `path`
out of the config and passes those as positional args (resolved against cwd),
keeping the config the single source for threshold/ignore/minLines/minTokens.

### A wrapped tool's own config wins; ours is only the fallback (human-requested by Ivett)

Installing habit-hooks must never override a developer's existing preferences,
so when a plugin wraps a third-party tool the **project's** config for that tool
is authoritative. A plugin ships its config as the answer to "this project has
none", never as an override — so a sensor may only reach for its bundled config
after establishing the project has no config of its own, and must not pass it
unconditionally.

The shipped `eslint.config.mjs` and `knip.json` are currently dead weight,
because neither sensor passes `--config` at all: the tools' own discovery finds
the project's config, which satisfies this rule by accident, but a project
*without* one falls through to the tool's defaults (knip) or a hard error
(eslint) rather than to ours. `docs/findings/09` and `docs/findings/17` pin both
halves — the fallback that is missing, and the project-wins behaviour that must
survive the fix. jscpd is the shape to copy: `jscpd.toml` names its config
explicitly, and the note above covers how its relative paths resolve.

Guard it in a plugin's acceptance spec with a case that writes **no** config for
the wrapped tool. Every case in `plugins/typescript/docs/typescript-plugin.spec.md`
copies the shipped config into the case dir first, which is why that suite
asserts the intent while the code does not implement it.

### The Node dev tools are one pnpm workspace, not three npm installs (agent decision)

`pnpm-workspace.yaml` makes the repo root, `plugins/typescript` and
`plugins/generic` one install with a single `pnpm-lock.yaml`, so CI runs
`pnpm install --frozen-lockfile` once instead of three `npm ci --prefix`. The
driver is supply chain, not tidiness: only pnpm ≥10.16 has an install cooldown,
and `.npmrc`'s `minimum-release-age=2880` refuses any version published in the
last 48h — the window in which a compromised-maintainer release is caught and
yanked. npm has no equivalent, so `package-lock.json` must not come back.
One workspace also means one root `.npmrc`; separate installs would each need
their own copy of that setting. `package.json` `pnpm.onlyBuiltDependencies: []`
blocks dependency install scripts (nothing here needs one — `pnpm
ignored-builds` reports none); it is an allowlist, so name a package rather than
lifting the block. That field is pnpm 10's home for it and moves to
`pnpm-workspace.yaml` in pnpm 11, so it travels with the `packageManager` pin —
which CI activates through Corepack, per the pnpm 10 → 11 gotcha below.

The layout the spec harnesses rely on survives: each plugin still has its own
`node_modules` to symlink into a case dir, and every tool the sensors spawn
(`eslint`, `knip`, `jscpd`) is a direct dependency, so it is still in that
tree's `.bin`. pnpm does not hoist transitive deps, so `.bin` is now only those
direct tools — do not add a sensor that spawns a transitive binary.

## Gotchas

### A git-backed spec case without a ceiling can rewrite THIS repo

The spec harness runs each case in `<repo>/.spec-runs/tmpXXXX/`, inside this
checkout. A case that shells out to git and forgets its own `git init` is
answered about habit-hooks itself — and `git branch -m main trunk` or
`git checkout -b feature` then *mutates your repository* (it renamed `main` here
while proving a case discriminates; recovered via `git branch -m trunk main`, no
commits lost). Give every git-backed section a
`✏️GIT_CEILING_DIRECTORIES` = `$PWD/..` step next to its `git init`, as
`## Scope` → `### Git-derived scopes` in habit-sensors.spec.md does: git's
upward walk then stops at the case directory and the case can only ever see the
repository it built. Older git-backed cases (habit-snooze.spec.md's
`## --until-changed`, and two in habit-sensors.spec.md) still lack it.

### `git diff --name-only` answers from the repo root, and quotes odd names

`changed_files._changed_paths` asks one batched `git diff` per run instead of
one per file (~39 ms each, in a tool that runs inside a hook loop). Comparing
its output to the paths we asked about needs three flags: `--relative` (else
git answers from the repository root and a project in a subdirectory matches
nothing), `-z` (else `café.py` comes back as `"caf\303\251.py"` and silently
matches nothing), and `--literal-pathspecs` — **not** for globs (exact-name
matching already makes over-matching harmless) but for pathspec *magic*: a key
like `:!src/a.py` otherwise reads as "exclude `src/a.py`" and silently drops it
from the answer, and `:(bad)x` makes git fail the whole call. Paths outside the
project are left out of the batch for the same reason: one of them fails the
call, which reads as "nothing changed" for every file in it. Pathspecs are also
chunked to ~100KB of argv — 24k paths in one call overflows ARG_MAX on macOS,
and `subprocess` raising `OSError` degrades to "nothing changed", i.e. every
snooze permanent, which is what batching had to avoid in the first place.

### A tool that resolves symlinks now hard-fails its sensor

Anchoring refuses a path outside the project. A source tree symlinked in from
outside the repo (`src/shared -> ../../shared-lib`) reported by a tool that
resolves paths before printing them (`ruff` prints `/private/...` on macOS for
exactly this reason) therefore fails that sensor — notice, findings dropped —
where before it merely produced an unportable key. `project_relative` retries
through `realpath` so a *project* reached via a symlink still anchors; a source
tree pointing outside the project cannot, and there is no correct repo-relative
name for it. Point the sensor at the real directory, or scope it out.

### knip runs a gated second pass in production mode (issue #59, rebuilt #99)

`plugins/typescript/src/habit_hooks_typescript/sensors/knip.js` runs knip
twice when — and only when — the config marks production patterns with a
trailing `!` on **both** `entry` and `project` (`configMarksProduction`,
reading the JSON `knip.json`/`.knip.json`/`package.json#knip`; a
jsonc/ts/js config JSON.parse cannot read falls back to a single pass so
glob patterns like `src/**/*` are never mangled). The default pass is
authoritative for every issue type; the `--production` pass contributes
only the dead-code keys in `DEAD_CODE_KEYS` (`files`, `exports`, `types`,
`nsExports`, `nsTypes`, `classMembers`, `enumMembers`), and only the
items the default pass did not already name (deduped by
`knipKey|file|name`). Those become a **separate** smell,
`test-only-dead-code`, sourced `knip:production:<key>` — code alive only
because a test references it, whose guide says to delete the test too.
This is a different smell from the default pass's `unused-file` /
`unused-export` on purpose: the two kinds have opposite fixes.

Gotchas: `--production` analyses NOTHING unless `!` is on BOTH `entry`
and `project` (a no-`!` config under `--production` silently reports zero
— so the gate never runs it there). Test files must be listed as
unmarked (non-production) `entry`, not `ignore`, else code reached only
by them looks unused to the *default* pass and is mis-coached as plainly
dead — which is why the shipped `knip.json` lists `tests/**` and
`src/**/*.{test,spec}.{ts,tsx}` as unmarked `entry`. As a belt-and-braces
guard the production pass never contributes a **test file** itself
(`isTestFile`/`TEST_FILE`): that pass drops test entries, so every test
file looks unused to it, and reporting one would invite deleting real
coverage. Unmapped and future knip keys pass through under their own name
as uncoached smells (`SMELL_BY_KEY[key] || key`) rather than vanishing,
and `classMembers`/`enumMembers` object maps are flattened before use so
they never reach `.map` (the crash #99 fixed).

### JSDoc nodes are not MultiLineCommentTrivia in ts-morph

`/** ... */` blocks are `SyntaxKind.JSDoc` (321) when attached to a
declaration, NOT `MultiLineCommentTrivia`. To find them, query both — see
`plugins/typescript/src/habit_hooks_typescript/sensors/comment.js`, which
collects the two kinds separately for exactly this reason.





### Bumping pnpm 10 → 11 needs Corepack, not auto-switch

pnpm 11 split its launcher: the main `pnpm` npm package owns
`dist/pnpm.mjs`, while `@pnpm/macos-arm64` (and siblings) ship only the
native loader. pnpm 10's `packageManager` auto-switch fetches only the
platform package, producing a binary missing its JS bootstrap —
`Cannot find module .../dist/pnpm.mjs`. Bootstrap pnpm 11 via Corepack
(`corepack prepare pnpm@<v> --activate`) or the official installer
instead. The standalone shim at `~/Library/pnpm/pnpm` is from the old
installer; once Corepack is on PATH, remove the shim so it stops
shadowing it.





### Indexing a jq object with `null` is an error, not a miss (issue #83)

`{"a": 1}[null]` **aborts** jq with `Cannot index object with null` (exit 5), so
a trailing `// .fallback` never runs — the whole sensor dies and every smell it
would have reported vanishes from the run. Every adapter that maps a tool's rule
ID through an object literal has to guarantee the key is non-null *before* the
lookup. The eslint sensor does it with `select(.ruleId != null or .fatal)`
(keeping `fatal`, which has no rule ID and is exactly what `parse-error` is for)
plus `--no-warn-ignored` to stop the commonest of them being raised at all.
`plugins/python/.../sensors/ruff.toml` has the same `{...}[.code]` shape and is
safe only because `--select` pins the codes and ruff spells a syntax error
`invalid-syntax` rather than `null` — if that ever changes, it fails the same way.

### A sensor named `ruff.toml` collides with ruff's config discovery

`plugins/python/sensors/ruff.toml` is a sensor spec (`command = ...`),
but ruff treats any file literally named `ruff.toml` as its own config.
A `ruff check` whose upward config-discovery walk passes through
`plugins/python/sensors/` hard-fails with `unknown field 'command'`.
Harmless in normal consumer operation — the file lives inside the
habit-hooks package, off the consumer's discovery path — but a future
dogfooding ruff run from inside that tree will be mystifying. Point ruff
at an explicit `--config pyproject.toml` if you hit this — never a
separate repo-root `ruff.toml`, which ruff prefers over `pyproject.toml`
on every local run and will silently shadow (and drift from) the real
`[tool.ruff]` config. The dogfooding config
(`.habit-hooks/config.toml`) already excludes the python-plugin subtree
for the same reason.

### Each released package needs its own publish environment

`.github/workflows/release.yml` maps each of the five PyPI packages to a
distinct GitHub environment because a pending trusted publisher is unique by
`(owner, repo, workflow, environment)` — five packages can't share one.
