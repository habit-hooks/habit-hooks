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

### Installing a plugin does not enable it, so every hint names the config line (agent decision)

`plugins` in `.habit-hooks/config.toml` is the only thing that makes a plugin
run; installing the package merely puts it within reach. A hint that named only
the install was therefore a loop with no exit — `pip install habit-hooks-python`
kept printing to someone who had just run it, and nothing in the line could
change the outcome. `recommend._hint` names enabling either way and drops the
install half for a plugin already on hand, asking `Resolver.has_plugin` — the
same question `require_plugin` asks, so "you configured a plugin that is not
there" and "you have a plugin you never switched on" can never disagree. Vendored
under `.habit-hooks/<name>/` counts as on hand, so the README's vendoring route
is never told to install what it has.

The spec cases vendor the plugin they are about rather than leaning on the dev
environment having it installed: what a doc case asserts must come from the files
the case writes, or its expected output silently depends on `uv sync`.

### Sensor `args` live in the sensor's own toml, not the plugin `config.toml` (agent decision)

A sensor's default CLI args (e.g. line-count's `--max 200`) live as `args = [...]`
in `sensors/<name>.toml` and expand into the command via `${args}`. They cannot go
in the plugin `config.toml` because `sensors = [...]` (the ordered list) and a
`[sensors.<name>]` table collide as the same TOML key. A project replaces them
wholesale via `.habit-hooks/config.toml` `[sensors.<name>] args = [...]`
(replace-on-override — `SensorOverride.args`, threaded in `loader._sensor_setting`).

**A command with no `${args}` refuses args rather than dropping them**
(`command_text._refuse_unusable_arguments`, the only place that knows both the
args and whether the command can take them): a `ConfigError`, unnamed so
`cli.run_console` prefixes the binary, exit 2 — the treatment #102 gives a config
key nothing consumes, and the reason this one stayed dead for seven of the eight
shipped sensors while `docs/config.md` promised it worked. A **plugin's** own
unusable `args` default is refused identically: there is no warning channel in
this stage that would not also fail the run (every sensor notice does, at exit 1,
with that sensor's findings dropped), so warning would cost a consumer more and
tell them less, and softening it would mean threading provenance through
`config` → `loader` → `Part` for a case no shipped plugin has. A run blocked by
someone else's packaging clears it with `[sensors.<name>] args = []` — an
override replaces wholesale, so the empty list is a value, not an absence.

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

### A config's schema is `config_schema.py`; finding and merging it is `config.py` (human-requested by Ivett)

`config_schema.py` answers what a config **is** and may **say**: the attrs types
(`Config`, `ScopeDefaults`, `SensorOverride`, `SmellOverride`), `settable()`
reflecting over their fields, `PLUGIN_CONFIG_KEYS`, the legal `uncoached` values,
and every refusal over all of that (`read_toml`, `reject_unknown`,
`reject_unknown_uncoached_value`). `config.py` is the loading around it: the file
it reads, the override chain, the plugin defaults, the `files` merge. The
dependency runs one way (`config` → `config_schema`), and the split keeps both
under the repo's own 200-line `oversized-file` gate.

The line is schema vs loading, **not** refusing vs the rest. An earlier
`config_guard.py` drew it the second way: named for a concept but holding schema
facts, so "what keys does `Config` accept?" was answered in two files and
`settable(Config)` reached across the boundary to describe a type it did not own.
Under size pressure again, move a whole concern across this line rather than
drawing a new one.

`detectors.py` is that move, made once (agent decision): the `Detector` type, the
kinds, and every refusal a `detectors` entry can earn, out of `config_schema.py`
whole — type *and* refusals, so "what may a detector say?" keeps one answer in
one file. It is the one config key with a vocabulary of its own, and it was a
third of the file. The shared key refusals (`reject_unknown`, `named_keys`) stay
in `config_schema.py` and are imported from `detectors.py`; that is why `Config`
imports `Detector` back under `TYPE_CHECKING` — annotation only, and the runtime
dependency stays one-way (`config` → `detectors` → `config_schema`).

### `load_config` names no binary; `run_console` does (human-requested by Ivett, issue #109)

`config.load_config(project_dir, config_path=None)` takes no argument for the
running binary's name, and must not grow one. A project's own transformer is a
separate process, and importing `load_config` is the only way one has ever had to
read `[scope] branchBase` — so a required argument here breaks every caller
outside this repository (it did), and a defaulted one only postpones the same
break. Loading raises an unnamed `ConfigError` (from `config_schema`, which owns
every refusal a config can earn); `cli.run_console` — already
the single place a `ToolError` is written to stderr — prefixes the binary's name
(`cli._named`) as it prints it, so each of `habit-sensors`, `habit-mapper` and
`habit-snooze` answers under its own name. Only `ConfigError` is prefixed: every
other `ToolError` is raised somewhere that knows the binary and says so already,
and prefixing those would double the name.

`run_console(program, body, argv)` hands `body` the raw argv and lets it call
its own `parse_args` rather than taking a parse callable as well (agent
decision) — the repo's own `max-args = 3` gate leaves no room for a fourth
parameter. Parsing inside `body` changes nothing: argparse's usage error is a
plain `SystemExit(2)`, not a `ToolError`, so it passes through the handler
untouched.

### A first-contact mistake answers in one line, never a traceback (agent decision, issue #114)

Asking for help, mistyping a config and running a tool you have not installed are
the three things a person does in their first ten minutes, and each used to
answer with a Python stack trace. Three separate seams keep them honest:

- **`habit-hooks` answers `--help`/`-h` itself**, as it already did `--version`.
  The pipeline is `habit-sensors $ARGS | habit-mapper`, so anything a stage
  prints on stdout lands on the pipe where `habit-mapper` expects findings JSON —
  forwarded, the usage text came back as a `JSONDecodeError` and was never seen.
  Its usage is `sensors.build_parser("habit-hooks")`: the stage's own parser
  under another `prog`, so what the help lists cannot drift from what is
  forwarded.
- **Every TOML this tool opens goes through `config_schema.read_toml`** — the
  project config, a plugin's, a sensor or transformer spec. It turns a
  `TOMLDecodeError` into the same unnamed `ConfigError` an unknown key raises:
  exit 2, naming the file and quoting tomllib, whose own text already carries the
  line and column. Unprotected it exited **1** — the code reserved for an
  enforced finding — so CI read a missing `]` as a smell in the code.
- **A command nobody installed is recognised by the shell's own phrase**
  (`part_output.COMMAND_NOT_FOUND`) and named, with what to do about it, in place
  of the failed part's stderr. Every other failure still quotes the tool back,
  because a tool that diagnosed itself is the one thing a reader can act on; a
  command that was never found has no words of its own. It stays the ordinary
  failed sensor — notice, failed run, `incomplete-run` at exit 1 — because a
  missing tool reading as "nothing to report" is the false-clean class #88 exists
  for. A plugin's Python helper that spawns its own tool must therefore answer
  `<tool>: command not found` rather than let `FileNotFoundError` escape
  (`plugins/generic/.../sensors/jscpd.py`): only the helper knows it was
  spawning, since `FileNotFoundError` from an `open()` is the same text about a
  file, and guessing from the traceback would mis-name a deleted source path as a
  missing command.

### `init` decides, reports, then acts — three modules, one direction (agent decision)

`initialise.py` decides (languages, plugins, what is missing) and prints nothing;
`init_report.py` turns a `Plan` into lines and does no I/O; `init_command.py` is
the flow — write the config, print, prompt, run. Same split, same reason, as
`rendering.py` against `mapper.py`: the decisions are the part worth testing
exhaustively, and a module that both decides and prompts cannot be.

**The install command it prints must match the environment habit-hooks is running
in** (`plugin_install.py`, packaging vocabulary in `plugin_packages.py`), or
`init` hands someone a command that cannot work — the support burden it exists to
remove. The environment is read out of `sys.prefix`, never inferred from "has no
pip", which catches a `uv venv` too:

- `uv-receipt.toml` → a `uv tool` install → `uv tool install 'habit-hooks[…]'`
- `relocatable = true` in `pyvenv.cfg` → a `uvx` cache entry uv owns, so nothing
  installed into it is the project's → the same durable command
- `extends-environment` in `pyvenv.cfg` → a `uv run --with` overlay → answer with
  the durable environment it names, never the temporary directory, which is gone
  when the run ends
- `pip` importable → `<sys.executable> -m pip install`
- otherwise (a `uv venv`) → `uv pip install --python <sys.executable>`

Spelling it with the **running** interpreter is what stops a plugin landing in a
different Python from the one habit-hooks runs from — a Homebrew install's
versioned `libexec` venv is the case that taught this.

`uv tool install` **rebuilds** its environment rather than adding to it, so one
command must name every plugin that environment has to end up *holding* — not
just the missing ones, and not just this project's, since one tool environment
serves the whole machine. Emitting one line per missing plugin uninstalls what
the previous line added, which the README told people to do for two releases. A
plugin on hand only by being vendored under `.habit-hooks/<name>/` is never
named: it is usually not on PyPI, and naming it fails the whole install.

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

When `jscpd --config <abs path>` loads a config, its `path: ["src"]` resolves
relative to the config file's directory, so a plugin-shipped config scans nothing
in the consumer repo. `plugins/generic/src/habit_hooks_generic/sensors/jscpd.py`
therefore reads `path` out of **its own** config and passes those as positional
args (resolved against cwd), keeping the config the single source for
threshold/ignore/minLines/minTokens. A project's own config needs none of this —
it already sits in the project — so that branch passes neither `--config` nor
paths and lets jscpd discover and resolve it (see the precedence note below).

Do not "make it uniform" by re-passing a discovered config's `path` positionally.
jscpd resolves a config's `path` to an **absolute** one where a positional
relative path stays relative, and it matches its `.gitignore`-derived globs
against whichever spelling arrives — so re-spelling their path changes which of
their own ignore rules bite (see the gotcha below). Standing aside is the only
arrangement in which a project's habit-hooks run is the run they get from `jscpd`
directly. It is also why the spec case with a project config runs its own `git
init`: cases run in `<repo>/.spec-runs/`, which this repo's `.gitignore` covers,
and jscpd's upward walk for a repository would otherwise find ours and scan
nothing.

### A wrapped tool's own config wins; ours is only the fallback (human-requested by Ivett)

Installing habit-hooks must never override a developer's existing preferences,
so when a plugin wraps a third-party tool the **project's** config for that tool
is authoritative. A plugin ships its config as the answer to "this project has
none", never as an override — so a sensor may only reach for its bundled config
after establishing the project has no config of its own, and must not pass it
unconditionally.

**The question has to be the tool's own** (#113, #120), or a project is told its
config was found where the tool would not have found it — and the sensor then
either speaks over a real config or withholds the fallback from a project that
has none. Reimplementing the tool's search is how that goes wrong, because the
shape is subtler than it looks: eslint looks a config up from each linted
**file's** directory, not from the directory it was invoked in
(`#locateConfigFileToUse`, eslint 10 `lib/config/config-loader.js`), so a
monorepo's `packages/app/eslint.config.mjs` is eslint's answer for that package
while being invisible to any walk from the project. A faithful copy of eslint's
six `FLAT_CONFIG_FILENAMES` walked up from `pwd -P` therefore answered "none"
and replaced a real config with ours.

**Let the tool answer wherever it can.** `sensors/eslint.toml` names no config,
runs eslint, and reaches for the shipped file only when eslint itself reports
`config-file-missing` ("couldn't find an eslint.config") — an answer that cannot
drift from eslint's, at the price of matching its prose. Match nothing broader
than that one failure: eslint exits non-zero for findings *and* for breakage, so
a fallback keyed on "it failed" would lend our config to a run that broke for the
project's own reasons and then call itself complete. If the prose ever changes, a
config-less project fails loudly rather than being mis-linted quietly, which is
the direction to be wrong in.

Ask the question yourself only where the tool offers no such signal, and then
copy the tool's list and its search shape, never another sensor's:
`sensors/knip.cjs` (`projectConfig`) checks knip's eight `KNIP_CONFIG_LOCATIONS`
plus a `knip` key in `package.json`, in the project directory only, because
knip's `findFile` never walks up.

**A config named through `[sensors.<name>] args` is the project's own too**, and
is the escape hatch for the one the tool's lookup cannot reach — so a sensor that
wraps a tool has to spell `${args}` or the project is overridden by the fallback
it wrote that config to avoid. eslint takes them in its **bare** run, which is
what makes that run succeed so the fallback branch is never entered; `knip.cjs`
forwards them and reads a `--config` among them with knip's own parser
(`node:util.parseArgs`, `config`/short `c`), so the file they name is in force for
the run *and* for the production gate. Ours is never named beside theirs: knip
takes the last `--config` it is given, so passing both would be us deciding
between two configs again.

**jscpd is the shape to copy** (issue #125). `jscpd.toml` hands the sensor
`--fallback-config`, never `--config`, and `config_arguments` names it only
after `project_configures_jscpd` finds nothing. What counts as "a config of its
own" is read out of the pinned tool rather than guessed — jscpd 4's
`prepareOptions` reads `.jscpd.json` in the directory it runs in, then a `jscpd`
key in `package.json`, and nothing else — so a project is never told its config
was honoured where the tool would not have looked. When the project does have
one the sensor passes **nothing at all** and lets jscpd discover it: that is the
only arrangement under which their habit-hooks run is the run they get from the
tool directly. An unparseable `package.json` counts as absent, as it does to
jscpd, so a typo in a file the sensor only peeks at cannot break the run.

A sensor that gates anything on the config's *contents* must read the config it
just decided to run: `knip.cjs` settles `configInForce()` once and threads it
into both `runKnip` and `configMarksProduction`. Re-deriving it by discovery is
how the `--production` pass stayed off in exactly the case it exists for.

Guard both halves in the plugin's acceptance spec: a case that writes **no**
config for the wrapped tool, and a case whose own config produces an answer the
shipped one cannot. `plugins/typescript/docs/typescript-plugin.spec.md` used to
copy the shipped config into every case dir, which is what let it assert the
intent while the code did not implement it; now no case writes one unless it is
the case demonstrating that a project's own wins.

### A sensor emits vocabulary smells only; `uncoached` answers for the rest (human-requested by Ivett, issue #111)

Translating a wrapped tool's key set into `docs/smell-vocabulary.md` is the
**sensor's** job, not the mapper's. A key the plugin has no smell for is dropped
at the sensor rather than forwarded under the tool's own name: forwarded, it has
no guide and no catalogue severity, so it can only fail a run and then decline to
explain why (`binaries` turned an untouched repository red). Adding a key to a
sensor's map therefore means adding the smell — catalogue entry, guide,
vocabulary line — or leaving the key dropped (`unlisted`/`unresolved` are
deliberately dropped until #124 gives them both).

**The eslint sensor is the deliberate exception**: it keeps
`[.ruleId] // .ruleId`. knip's key set is knip's own, but an eslint rule ID comes
from a config the project wrote, so an unmapped rule is one the project turned on
itself and forwarding it saves running lint separately. That is the test for any
future wrapped tool — whose vocabulary is it?

Whatever still arrives uncatalogued is the core's decision, not the sensor's: the
root `uncoached` key (`suggest` default / `ignore` / `enforce`) replaces the old
`ENFORCED` fallback in `rendering.severity_of`. It is a **root** key because
`[smells]` is keyed by smell name and a scalar there collides exactly as
`sensors = [...]` does with `[sensors.<name>]`. `ignore` drops the finding
through `is_disabled`, the same seam as `[smells.<name>] disabled`; a
`[smells.<name>] severity` is the project deciding about that one smell and wins
over all three values (`rendering._is_uncoached`).

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

### `docs/` is user-facing documentation that doubles as acceptance test (human-requested by Ivett)

Every `.spec.md` under `docs/` is documentation first: it is written for someone
learning how habit-hooks behaves, and pytest executing each case is what keeps
that documentation honest. A bug fix does not earn a place there. Its regression
test is a unit test under `tests/`, named for the behaviour it protects — even
when the bug was first reproduced as a `docs/findings/NN-….spec.md`, which is a
reporting convenience for review and not the fix's home. The question to ask of
a case before adding it to `docs/` is whether a user reading it to learn the
tool would want it; if the honest answer is "it is here so this bug cannot come
back", it belongs in `tests/`.

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

`plugins/typescript/src/habit_hooks_typescript/sensors/knip.cjs` runs knip
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
coverage. `classMembers`/`enumMembers` object maps are flattened before
use so they never reach `.map` (the crash #99 fixed).

### A shipped ESM config resolves its imports from where it is, not from the project

`eslint --config <abs path>` reads the file from wherever habit-hooks is
installed, and a bare `import` inside it resolves against **that** directory —
for a consumer, a Python `site-packages` tree with no `node_modules` anywhere
above it. `eslint.config.mjs` therefore died on
`ERR_MODULE_NOT_FOUND: Cannot find package '@typescript-eslint/eslint-plugin'`
the moment the sensor started naming it, while passing in this repo by pure
luck of layout (`plugins/typescript/node_modules` is one of its ancestors). It
now resolves its parser and plugin through `createRequire` anchored at
`process.cwd()` — the project, which is where eslint itself came from
(`spawn.py` puts `<project>/node_modules/.bin` on PATH). Any future config a
plugin ships and passes by path needs the same treatment; ESM ignores
`NODE_PATH`, so there is no environment-level escape.

The other half of that arrangement is knip's, and it is the opposite of jscpd's:
knip resolves a config's relative `entry`/`project` globs against **cwd**, not
against the config file, so the shipped `src/**` patterns still mean the
consumer's tree when passed by absolute path.

### JSDoc nodes are not MultiLineCommentTrivia in ts-morph

`/** ... */` blocks are `SyntaxKind.JSDoc` (321) when attached to a
declaration, NOT `MultiLineCommentTrivia`. To find them, query both — see
`plugins/typescript/src/habit_hooks_typescript/sensors/comment.cjs`, which
collects the two kinds separately for exactly this reason.

### A Node helper named `.js` lets the consumer pick its module system (issue #112)

Node never reads a `.js` file to decide whether it is CommonJS or ESM: it
walks up from the script to the nearest `package.json` and reads `"type"`
there. A CommonJS helper named `.js` therefore dies on its first line —
`ReferenceError: require is not defined in ES module scope` — in any
project declaring `"type": "module"`, the default a new TypeScript
project is scaffolded with. The helper only lands inside that scope on
the installs that put the package under the project directory: the
vendoring route the README advertises (`.habit-hooks/<plugin>/sensors/`)
and a project-local `.venv/`. `uv tool install`/`uvx` put it outside and
escape by luck of layout, so neither reproduces the bug. Hence
`sensors/knip.cjs` and `sensors/comment.cjs` — the extension settles the
question inside the file, where a consumer's manifest cannot reach it,
and it survives vendoring, which a sibling `{"type": "commonjs"}`
`package.json` would not (it would have to be vendored too). Ship any
future Node helper as `.cjs`, or as real ESM.





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

### jscpd ignores a checkout that *lives* under a path its own `.gitignore` covers

jscpd's `initIgnore` turns each line of `<cwd>/.gitignore` into globs, and a line
containing a slash becomes `**/<line>/**` — matched against the **absolute**
paths a config-derived `path` produces, filesystem prefix and all. A checkout at
`…/habit-hooks/.claude/worktrees/agent-x/` therefore ignores its entire self
against this repo's own `.claude/worktrees/` line: zero files scanned, zero
clones, exit 0, a clean run. Proven by two fixtures identical but for their path
(ordinary → the planted clone; under `.claude/worktrees/` → nothing), and by
running `jscpd` bare in a worktree, which is equally blind. It is the tool's
behaviour, not the sensor's — and the sensor reproducing it exactly is the point
of the precedence rule above.

The consequence for us: **inside an agent worktree `uv run habit-hooks --all`
proves nothing about jscpd.** An ordinary checkout and CI are unaffected (no
ignored segment in their paths). To check duplication from inside a worktree,
run jscpd with positional relative paths, as the fallback branch does.

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
