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
in-repo plugins live under `plugins/<name>/src/habit_hooks_<name>/` and are
installed editable by `uv sync` for dev. Keeping them in-repo is only a dev
convenience — they do not need to live here. `tests/conftest.py`'s
`SHIPPED_PACKAGES` builds + installs every released wheel into a throwaway venv
and `tests/test_installed_wheel_smoke.py` asserts a real finding comes out; it
is the gate that catches "installed runs can't locate plugins", so a plugin
missing from that tuple is a plugin whose packaging nothing checks. `${dir}` in a sensor command resolves to the plugin's package-data dir,
so helper-script paths (`${dir}/line-count.py`, `${dir}/../.jscpd.json`) keep
working once the layout is preserved under the import package.

### A plugin helper imports its neighbours as top-level modules (agent decision, issue #132)

A sensor helper is spawned as a loose script (`${python} ${dir}/pmd_sensor.py`),
so its own directory is `sys.path[0]` and a module beside it is a plain
top-level import — `from pmd_ruleset import ruleset_of`, never
`from .pmd_ruleset import`, which has no package context to resolve against.
That works wherever `${dir}` points, so one spelling serves the installed
package and a vendored `.habit-hooks/<plugin>/sensors/` copy alike. Vendoring
never blocked a helper from having a neighbour: the *override chain* is
per-file (each file resolved independently, so one guide can be replaced
without copying a plugin), but a sensor already needs its `.toml`, its helper
and its data (`pmd-ruleset.xml`) side by side in whichever directory wins.

A unit test therefore loads a helper the way a run loads it —
`plugins/java/tests/conftest.py` puts the sensors directory on `sys.path`, as
the interpreter does for a script. Reaching the same code as
`habit_hooks_java.sensors.pmd_sensor` is a load path no run ever takes and the
only one under which that import fails, so testing through it would force the
production code into a spelling production cannot use.
`plugins/java/tests/test_a_vendored_sensor_finds_its_neighbour.py` is the gate,
and it runs the copy under `python -S`: this checkout has the plugin installed,
so without that a package-absolute import would pass on site-packages and prove
nothing about the files the case copied.

`sensors/spawn.py` pins `PYTHONSAFEPATH` empty for the same reason it pins
`PYTHONIOENCODING`: that variable's whole effect is to drop the script's own
directory from `sys.path`, so a consumer who hardens their environment with it
would get a `ModuleNotFoundError` traceback in place of coaching.

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

### A whole-project scan measures what git keeps, never what is on disk (human-requested by Ivett, issue #142)

`project_scan.files_in()` — `scope._every_file`'s only source — asks
`git_listing.project_files` (`git ls-files --cached --others --exclude-standard`,
so tracked **plus** brand-new-but-not-ignored) instead of walking `rglob("*")`.
Before #142, `--all` was the one mode that never asked git, so it alone measured
`dist/`, `.next/` and tool caches: a real monorepo enumerated 843 `.ts`/`.tsx`
for the 321 it keeps, and its owner had to hand-write `!**/dist/**` into
`[files]` to get a usable run. Every git-derived mode already skipped those, so
this is what stops one project having two universes. The narrowings after it are
unchanged — `_source_files` still drops what the work tree lost and still applies
`[files]` — and discovery stays opt-in, so `config.files is None` returns `[]`
before git is asked anything.

Git's silence is never "nothing to scan" (the #81 rule): outside a repository,
with no git installed, or on any failure at all, the empty answer falls back to
the `rglob` walk. Over-scanning is a nuisance; scanning nothing reports a whole
tree clean unread. That `or` is also why the whole-tree cases need no guard of
their own — a project the surrounding repository ignores outright answers empty
and falls back on its own.

**`git_listing.ignores_directory` exists for the answer that is *partial*, not
the one that is empty.** It gives git's list up when the repository above the
project ignores the project directory. An outer repository can force-add one
file under a path it ignores; git then lists that file and nothing else, and a
partial list is the shape the `or` cannot see — it looks like a real answer, so
the run measures one file and pronounces every other file clean without reading
it. `--no-index` is what makes the question about the ignore rules rather than
the index: by default `check-ignore` calls a directory holding anything tracked
"not ignored", so without it the guard stands down for exactly that project.

**Ask about the project by name, and only if it is not a repository root.** The
question was `check-ignore --no-index --quiet .`, and both halves of that were
wrong. A repository never ignores its own root, but `*` — the allow-list opening
that a careful `.gitignore` very often has — matches the name `.` like any
other, so a project reported *itself* ignored and threw away a perfectly good
file list; #142 then silently did not apply to it. So `rev-parse
--show-toplevel` settles the root case first. Below a root the rules really are
consulted, and `.` there resolves against the *project's own* `.gitignore`
rather than the one deciding about the project — hence the full path,
`check-ignore --no-index --quiet -- <project_dir>`. Seven shapes were measured
(root ordinary / root with `*` / clean subdir / ignored subdir / subdir with its
own `*` / own repo inside an ignored tree / no repo) and only this pairing gets
all seven right.

The gates are in `tests/test_a_scan_skips_what_git_ignores.py` (the two `*`
cases, one per half of the fix) and
`test_one_force_tracked_file_never_becomes_an_ignored_projects_whole_scope`,
which is the only test that fails when the guard is dropped altogether.
Measured, because the tempting justification is wrong: forcing
`ignores_directory` to `False` leaves **every spec case passing**, so "our own
`.spec-runs/` would scan nothing" does not motivate the guard, and neither does
`test_a_project_in_somebody_elses_ignored_tree_scans_everything`, which passes
with the guard gone.

A **submodule** is the one deliberate loss: `ls-files` names it as a single
gitlink *directory*, never the files inside. Keeping it out is right — `git diff`
does not descend into one either, so this makes `--all` agree with the modes it
used to contradict, and the submodule gates itself in its own repository. But a
scope that silently shrinks and then renders ✅ is the false clean this tool
exists to stop, so `scope_notices.submodule_notices` names each one on stderr.
It is advisory and leaves the exit code alone, matching every other scope notice
(a run that scanned *nothing* still exits 0). `--file` is excluded because that
path is one the caller typed rather than one git named; a directory given to it
is already answered by `_named_file_notice`.

**Ask the index what a submodule is, never the filesystem.** A submodule is a
gitlink, which git records with mode `160000`, so `git ls-files --stage` answers
exactly and `.gitmodules` never has to be parsed. `Path.is_dir()` cannot answer
it: it follows symlinks, so a *tracked symlink to a directory* (mode `120000`)
is indistinguishable from a gitlink — and a symlinked `node_modules` is pnpm's
ordinary layout, so the filesystem question tells an everyday JavaScript project
that its dependency tree is a submodule. Reaching for `is_symlink()` instead
would still be the wrong question with a luckier answer.

**And say it only about a submodule whose files the run wanted.** The claim is
"your scan is smaller than you think", which is false where `[files]` excluded
the directory regardless — the typescript plugin's own `!**/node_modules/**` is
the case that proved it. `_held_source_this_run_wanted` lists what the submodule
really holds (`git ls-files` inside it) and puts those paths through `[files]`;
matching the *directory name* would silence every notice, because a source glob
like `**/*.py` never matches a bare directory. `scope_notices` owns **both**
halves of that judgement even though `git_listing` knows what a gitlink is and
`scope` owns the narrowing: a notice right about one half and wrong about the
other is worse than none, and neither of those modules can state the thing being
claimed. `path_globs.matching` exists so it can ask the `[files]` question
without importing `scope`, which is its own caller.

The split follows the repo's existing precedents, in one direction throughout:
`scope` → `project_scan` → `git_listing` → `git_command`. `project_scan.py`
holds what a project *has* against `scope.py`'s what a run *measures*.
`git_listing.py` is what git says about the **working tree as it stands** (which
files, which ignored) against `git_history.py`'s what git **remembers** between
revisions — `git_history` asks it only to widen a diff with untracked work.
`git_command.py` is **how** any of it is spawned (cwd, UTF-8, empty stdin,
`OSError` → `None`) against **what** is asked. All three moves were forced by the
200-line `oversized-file` gate the dogfood run enforces, and each moved a whole
concern rather than trimming prose.

**Every empty scope says why it is empty**, and a `[files]` that is set and
matched nothing was the last silent case. A project whose `.gitignore` covers
its own source tree keeps no files git will name, so it scanned zero files and
rendered ✅ — a run that *measured* nothing, indistinguishable from one that
*found* nothing, which is the #88 class. `NOTHING_MATCHED_NOTICE` names both
possible causes, because neither is visible from the other: `[files]` may be too
narrow, or git may be ignoring the very tree it was written for.

A **non-empty** scope that lost some files is deliberately left silent. Measured
on a project with an ordinary `.gitignore`: eight `.py` files dropped, seven of
them `.venv`, `node_modules` and `dist`. Naming them is noise, and finding them
at all needs the disk walk this change exists to avoid — so the empty scope,
where the loss is total and the run is worthless, is the case worth catching.

Two things `git_command` settles for every caller above it. A non-zero exit
yields **empty**, never the output — `rev-parse --abbrev-ref HEAD` in a
repository with no commits exits 128 *and* prints `HEAD`, so trusting stdout
would publish that as a branch name (`tests/test_git_command.py`). And
`files_in`'s two branches must **sort** alike: the walk builds its own strings
from `os.sep`, and `\` and `/` sort differently, so without `as_posix()` the
same project comes back in one order from git and another from the walk. No
caller ever sees a backslash — `scope._placed` normalises again through
`project_paths` — so this is about the branches being interchangeable, not about
a spelling escaping into a finding.

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

### Findings that render the same guide are one finding (agent decision, issue #140)

`merged_findings.merged()` is the third module across that same line: `mapper.run`
folds findings together *before* `render_finding` sees any of them, so
`rendering.py` still renders exactly one finding and knows nothing about this.
Two sensors can see one smell (eslint's `max-lines` and generic's `line-count`
both report `oversized-file`) and one sensor can report a smell many times over
(jscpd emits a finding per clone), and the mapper prints one block per finding —
so each of those was another copy of the same ~200-word guide.

**The key is the smell AND the guide it resolves to, never the smell alone.** One
guide printed twice is the whole waste being removed, so merging exactly what
renders alike is correct by construction. Merging by smell alone is a
*misrouting bug*: `high-complexity` routes to the python plugin's guide for a
`.py` file and to generic's for a `.ts` one, and folding them together coaches a
TypeScript file in Python (or silently drops a Python file's Python guidance,
depending on plugin order). Keying on `language` instead fixes nothing, because
`generic` declares none. The smell stays in the key for two reasons: a
`[smells.<name>] guide` override can point two smells at one file and their
banners still name them apart, and `rendering.severity_of` is per smell — keyed
on the guide alone, a *suggested* finding could absorb an *enforced* one and
lower the run's exit code. `merged` takes the resolution as a **callable**
so it never learns about `Config` or `Resolver`; `rendering.resolve_guide` is
public for that one caller, and the dependency stays one-way.

Merging is the **mapper's**, never the sensors stage's: what a sensor emitted is
the run's own record, read by `habit-snooze`, so a snooze key must not depend on
who else saw the same file.

**The merged finding's facts.** Issues concatenate in arrival order. A top-level
key (`language`) is **first non-null** — the runner leaves it unset for
`generic`, so a null must not out-rank a real answer. A smell-level `details`
key is kept when only one finding states it (`line-count`'s `maxAllowed`) and
**dropped when two state it differently**: jscpd's `lines`/`tokens` describe one
clone pair, and publishing the first pair's numbers as the whole finding's would
teach a wrong number where a missing key renders as nothing. No shipped guide
reads finding-level `details` — every reference in `guides/**` is a per-issue
value inside a loop over `issues` — but `docs/sensor-interface.spec.md` and
`docs/habit-mapper.spec.md` both teach plugin authors to read it, and
`render_runner` hands a fix runner the whole finding.

**Deduplication is across findings only, never within one.** A sensor's own issue
list is authoritative: it meant the seven long functions it reported. Three
shipped sensors (`pmd`, `phpmd`, `comment`) key by file, give a line and give
**no column**, so two of their issues on one line — `int a = 1, b = 2;`,
`$a = 1; $b = 2;`, a block and a line comment — are one place to any identity
built from the place alone, and only the tool's `message` tells them apart. #140
is about two *sensors* reporting one thing, so each finding's own list is kept
whole and only what an earlier finding already named is dropped.

An issue is identified by its `key` and **the place it names**, and by nothing
either tool said in its own voice: `source` and `message` disagree precisely
because they are two tools. `PLACE_FIELDS` is `file`, `line`, `column`,
`startLine`, `endLine` — the contract's own location fields plus the range
`duplicated-code` spells instead of a line. Every one is load-bearing and has a
test that dies without it. Widening the identity only ever keeps issues apart,
which is the safe direction; narrowing it silently deletes findings.

**Known consequence: `duplicated-code` loses its pairing.** jscpd emits a finding
per clone pair, so three pairs merge into one six-entry list and which occurrence
matched which is no longer visible. Accepted deliberately — the guide repeated
per pair was the #140 complaint and the token saving is large, and arrival order
keeps each pair adjacent in the list. Restoring the pairing means teaching the
guide to group, not un-merging the finding.

**A fix runner sees the merged finding, not the sensor's.** `render_runner` runs
once per finding, so a runner judging what it is handed judges more issues than
any one sensor reported — and its exit code sets whether the run blocks. Two
`oversized-file` findings of one issue each, under a runner that fails only a
single-issue finding, exit 1 before merging and 0 after. That is the intended
semantics (one guide, one judgement), but it is consumer-visible, so a runner
must be written against a whole smell rather than a single sensor's report.

The other half is at the sensor: `eslint.cjs`'s `FILE_LEVEL_SMELLS` drops the
position from a smell whose guide lists files rather than lines
(`includes/file_level_issues.md`), because `max-lines` reports at the first line
past the limit and `line-count` names no line at all — disagreeing there is what
stopped the two being recognised as one observation. `parse-error` is file-level
too and is deliberately **not** in that set: its position is where parsing really
failed, and nothing else reports it about a file eslint can read. The keys stay,
`null`, so an eslint issue's `details` keep one shape.

### What a failure *says* is `part_output.py`; how much of it is `diagnosis.py` (agent decision)

`part_output.py` decides what a finished part's output means — which exit codes
can be trusted, which failure a reader is looking at, and the words for each.
`diagnosis.py` is the quoting underneath it: `DIAGNOSIS_LINE_LIMIT`, `as_text`,
`keep_both_ends`. How much of a tool's own output to carry back is a separate
question from what the failure was, and it is the half with the reasoning worth
keeping in one place — a tool that dies mid-warning-storm produces megabytes,
while a Python traceback names its exception on the *last* line, so neither end
alone can be dropped.

The dependency runs one way (`part_output` → `diagnosis`), the same direction
and for the same reason as `config` → `config_schema` and `mapper` →
`rendering`. Under size pressure again, move a whole concern across this line
rather than drawing a new one.

### How an argv is run is `spawn.py`; what a broken part becomes is `broken_part.py` (agent decision)

`spawn.py` runs an argument list: the project's tool bins on PATH, a process
group of its own, UTF-8, the deadline, and a bare `argv[0]` resolved to the file
this machine runs for it. It knows an argv and never whose it is.
`broken_part.py` is the boundary that does — it refuses a part before anything
is spawned (`posix_shell`, and a tool the project cannot run) and turns every
spawn failure into the `SensorError` a notice is made from, named for the part
that earned it.

Neither imports the other: `run_part` takes a callable rather than a `Spawner`,
so `broken_part` imports `posix_shell`, `batch_shell`, `part_output`, `model`
while `spawn` imports `project_paths`, `deadline`, `live_commands`,
`batch_shell`, `part_output`, and `execution` is the one module that imports
both. It is the same split, and the same 200-line `oversized-file` gate behind
it, as `config` → `config_schema`, `mapper` → `rendering` and `part_output` →
`diagnosis`. Under size pressure again, move a whole concern across this line
rather than drawing a new one.

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

### A test whose answer differs by platform pins the platform, through `host_platform` (agent decision)

`host_platform.is_windows()` is the one seam every platform decision in this
tool asks through, so it is also the one seam a test pins. A test qualifies
whether or not it is failing today: an argv budget, a venv's bin directory, a
`command` part's shell recipe, a `shlex.quote`d path — anywhere the correct
answer differs between a Mac and Windows, the test states which platform it is
answering for (`platform_probe.on_windows(monkeypatch)` /
`off_windows(monkeypatch)`) and asserts that platform's own answer, never
whichever one the machine running the suite happens to be. `tests/platform_probe.py`
is the one place this is done — every pinning site imports it rather than
hand-rolling `monkeypatch.setattr(host_platform, "is_windows", ...)`, so there
is one seam and one docstring explaining why it matters, not four drifting
copies. `platform_probe.A_SHELL_TO_RUN_IT_WITH` is the other half: some POSIX
behaviour (a shell must never let a filename execute its own contents) can
only be shown by really running a shell recipe, which `off_windows` alone does
not conjure onto a machine that has none — that stays a `skipif`, a question
about the host rather than the platform seam. `A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF`
and `A_MACHINE_THAT_DOES_NOT` are that same `skipif` for the same reason:
whether a bare `jscpd` names `jscpd.CMD` is `shutil.which`'s answer, keyed off
`sys.platform` inside the stdlib, where no seam of ours reaches.

Without pinning, a test reads its expected answer off the host it happens to
run on: green on the author's Mac, red the moment the Windows leg of CI runs
the same suite, and — because nothing about *why* was ever asserted — evidence
of nothing on either. It happened three times in this repo before the pattern
was named, the third slipping in after the first two were already called out.
Where the shell a test spawns is incidental to what it proves (a scope
narrowing, an argv budget split), spelling it as an `argv` part instead is
better than pinning it at all: nothing platform-specific is left to assert.

## Gotchas

### Two agents running pytest in one checkout fail each other's tests

Two suites keep their working state *inside the checkout* rather than in a
per-test temp dir, so a second concurrent `uv run pytest` walks into the middle
of the first one's run:

- the spec harness runs every case in the shared `<repo>/.spec-runs/`
  (`conftest.py::_case_root`), and
- `tests/wheelhouse.py` builds the released wheels and installs them into
  throwaway venvs, which `test_installed_wheel_smoke.py` and
  `test_installed_plugin_packaging.py` then run.

Both go red under concurrency and both pass on an unchanged re-run — 15 spec
failures in one session, 6 packaging failures in another, none of them real. A
**unit** failure in `tests/` is always real; a failure in either of those two is
not evidence until it survives a re-run in a quiet tree. Give each agent its own
worktree (`git worktree add ../habit-hooks-<task> -b <task> main`) when more than
one will run the suite, and note that inside a worktree the jscpd gotcha below
makes `uv run habit-hooks --all` prove nothing about duplication.

### A throwaway git fixture names its directory, or it commits to THIS repo

`GIT_CEILING_DIRECTORIES` is not the guard for a scratch script. It stops git
walking *up* to find a repository — and a script whose working directory is
already this checkout never needs it to. `git init` on an existing repository is
a harmless re-init, so nothing refuses; the `git add -A` and `git commit` that
follow land on the real thing. It has happened: 45 files of four agents'
uncommitted work swept into a commit titled `init`, and the dogfood
`.habit-hooks/config.toml` overwritten by the fixture's own.

The shape that does it is a multi-line `bash` command where only the first line
is guarded:

    cd $SCRATCH/proj && git init -q && ...   # cd fails, the line is skipped
    git add -A && git commit -m init         # no guard: runs HERE

So: **every git command in a fixture spells `git -C <dir>`**, and a fixture
never runs a bare `git` after a `cd`. A failed `cd` then targets nothing instead
of targeting this repository. `git add -A` outside a `-C` is the specific thing
to never write.

Recovery, if it happens again: `git reset --mixed <the real HEAD>` keeps every
change as a working-tree modification and loses nothing, because the accidental
commit was `git add -A` and therefore captured everything. Then restore whatever
the script overwrote from HEAD.

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





### An unmapped rule or code must never reach a bare lookup (issue #83)

Both sensors map a tool-supplied string — an eslint rule ID, a ruff code —
through a table of the smells this plugin knows about, and the tool is free to
send a string neither table has an entry for. The hazard was first named
against the sensors' old jq pipelines: `{"a": 1}[null]` **aborts** jq with
`Cannot index object with null` (exit 5), so a trailing `// .fallback` never
ran and the whole sensor died, taking every finding in the run with it. Neither
sensor pipes through jq any more — both are native helpers now — but the
underlying hazard (trust an external string as a lookup key, and something
breaks on the miss) is still real in each language, and each guards it in its
own way:

- **ruff** (`sensors/ruff_sensor.py`) maps a code through
  `CODE_SMELLS.get(entry["code"])`. A dict's `.get` answers `None` for a code
  outside `--select`, and `findings` drops that entry rather than forwarding or
  crashing on it — the same "drop what the plugin has no vocabulary for" rule
  the knip sensor already follows (see "A sensor emits vocabulary smells only"
  below).
- **eslint** (`sensors/eslint.cjs`) maps a rule ID through `SMELL_BY_RULE`, a
  `Map` rather than an object literal. A plain object answers
  `SMELL_BY_RULE["constructor"]` with a function off `Object.prototype`, which
  `JSON.stringify` then drops silently — the finding would keep its issue but
  lose its `smell` key, with nothing in the run saying why. A `Map` has no
  prototype chain, so `.get` answers `undefined` for anything absent, and
  `smellOf` falls back to forwarding the rule ID itself (the deliberate
  exception in "A sensor emits vocabulary smells only" — an eslint rule ID
  comes from a config the project wrote, unlike knip's own vocabulary).

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

`plugins/python/sensors/ruff.toml` is a sensor spec (`argv = [...]`),
but ruff treats any file literally named `ruff.toml` as its own config.
A `ruff check` whose upward config-discovery walk passes through
`plugins/python/sensors/` hard-fails with `unknown field 'argv'`.
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

`.github/workflows/release.yml` maps every PyPI package to a distinct GitHub
environment because a pending trusted publisher is unique by
`(owner, repo, workflow, environment)` — two packages can't share one. A package
new to PyPI also needs its pending publisher registered there before the tag, or
its leg of the publish matrix fails while the rest succeed.

### The plugin floor is raised with the version, and the tap bump goes via a PR

Two things about a release that are silent when forgotten (agent decision):

- The core floors each plugin at the release's own minor, so every plugin
  specifier in the core's `pyproject.toml` moves on a minor bump.
  `pip install -U habit-hooks` upgrades a dependency only when the new core
  stops being satisfied by the installed one, so a floor left behind hands
  someone the new core with last release's plugins — where nearly every fix
  lives. `tests/test_the_plugin_floor_tracks_the_release.py` gates all three
  halves: the floor tracks the version, the release satisfies its own floors,
  and the plugins ship at it.
- The `habit-hooks/homebrew-tap` bump belongs in a **pull request**, not a push
  to its `main`. `brew test-bot` builds bottles either way, but `publish.yml`
  (`brew pr-pull`) attaches them from a PR number — pushed straight to main,
  1.2.1 shipped with no bottles and every `brew install` builds from source.

### A `~=<minor>` floor cannot ship a release candidate (agent decision, #133/#134)

The floor is spelled `habit-hooks-<plugin>>=1.4.dev0,<2`, never `~=1.4`, and the
reason only shows up at a tag. `~=1.4` **is** `>=1.4, ==1.*`, and by PEP 440
ordering `1.4.0rc1` sorts *below* `1.4` — so a release candidate declares floors
its own plugins cannot satisfy, and `pip install habit-hooks==1.4.0rc1` dies
with `Could not find a version that satisfies the requirement
habit-hooks-generic~=1.4` while `1.4.0rc1` is sitting in the listed versions.

**No pre-release flag lifts it.** `--pre`, `--prerelease=allow` and
`UV_PRERELEASE` were all measured and all ineffective: they are policy over
*which candidates a resolver may consider*, and this is the specifier's own
ordering excluding the version outright. Reach for the spelling, never a flag.

`>=1.4.dev0,<2` loosens **only** the release candidates of `1.4.0` itself.
Compared version by version against `~=1.4`, the two answers differ on
`1.4.dev0`, `1.4.0a1` and `1.4.0rc1` and agree everywhere else: `1.3.1` and
`1.3.2rc1` are still refused, `1.4.1rc1` and `1.5.0rc1` were already admitted by
`~=1.4`, and `2.0.0rc1` is still refused (PEP 440 forbids `<V` matching a
pre-release of `V` itself). The same spelling serves the rc and the final
release, so nothing is rewritten between them — which is the point, since a
floor rewritten at the tag is a floor nobody tests.

The gate is `test_this_release_satisfies_the_floors_it_declares`, which asks
`packaging`'s `SpecifierSet`/`Version` rather than reading the string — the same
question pip asks, so it cannot answer differently.

### A sensor names the tool it wraps, and is handed the file that runs it (agent decision)

Windows' `CreateProcess` appends `.exe` to a bare command name and nothing else,
while `shutil.which` applies the whole of `PATHEXT`. Every Node tool a plugin
wraps (`knip`, `eslint`, `jscpd`) is installed as a `.cmd` shim and `pmd` as a
`.bat`, so `missing_tools` clears each of them and anything spawning them by
name then answers `jscpd: command not found` with the tool sitting right there.
`project_paths.tool_executable` is the single lookup everything asks.

**A part's own `argv[0]` is only half of it, and the half no shipped sensor
uses.** Every one is `argv = ["${python}", "${dir}/<helper>.py", ...]` or
`["node", "...cjs", ...]`, and the helper spawns `jscpd`/`pmd`/`php`/`deptry`/
`ruff` itself, one process further in — where the tools that actually go missing
on Windows go missing. `sensors/spawn.Spawner._runnable` still resolves a bare
`argv[0]`, since off Windows it names the very file the spawn's own search would
have reached; only a **bare** name is resolved, because a path (`${python}`,
`${dir}/helper.py`) is read against the directory the command runs in, and every
argument after the first is an argument whatever it looks like.

The other process gets there by **naming the tool in the recipe**:
`${detector:<name>}` (`sensors/named_tools.py`) expands to the file
`tool_executable` answers with, for a tool the plugin declared in its
`config.toml` `detectors` — the same list `missing_tools` cleared, so a tool a
project was told it has is a file its sensors can be handed. Every shipped
Python-plugin sensor that wraps a tool spells it — `line-count` wraps none —
and each helper reads that file from `sys.argv[1]`, always the first argument
after the script, so the five stay symmetric. Three things follow from the core
holding it, rather than a helper:

- A tool that is declared and simply absent is answered **before** the spawn
  (`broken_part.run_part`), as the notice + failed run a missing command has
  always been. A helper never sees it, so a helper cannot get it wrong.
- Every program the arguments reach is asked whether `cmd.exe` would read them
  (`batch_shell`), the named tool included — the guard that matters for `pmd.bat`.
- A name no active plugin declares, or one declared `node-module`, is refused
  when the config loads. Run-wide rather than per-plugin, because a root
  transformer has no plugin of its own;
  `tests/test_a_plugin_declares_the_tools_it_names.py` reads each plugin's own
  specs against its own declarations so that breadth cannot hide a missing
  declaration.

This replaced four byte-identical `sensors/tool_spawn.py` copies — one per Python
plugin, because every plugin's `pyproject.toml` declares `dependencies = []` and
none may import `habit-hooks` or a sibling. That constraint is unchanged and is
why the answer is a placeholder the core expands rather than a shared module: a
recipe is data, and data crosses a boundary an import cannot.

**The TypeScript plugin keeps `sensors/project_tool.cjs`**, and cannot use any of
this. Its wrapped tools are `node-module` detectors, never spawned by name at
all (`node` itself is a `command`, and is every one of its sensors' `argv[0]`):
it finds the package under the project's own `node_modules`, reads its `bin`
entry, and runs that file with `process.execPath`. `shutil.which` finding a
`.cmd` shim is no use to Node — `spawnSync` has refused to run a `.cmd` or
`.bat` outright since its CVE-2024-27980 mitigation (`IsWindowsBatchFile` in
`spawn_sync.cc`), still unconditional in Node 22, and the `--security-revert`
flag that once bypassed it was removed in Node 22.0.0. `shell: true` is not the
way round it either: it hands the argv to `cmd.exe` to reparse, and a sensor's
arguments are filenames straight out of a checked-out branch, which this repo
treats as hostile.

**What was given up.** A helper guards the whole command at the real spawn; the
core can only guard what it can see, which is the part's own arguments. What a
helper synthesises out of them is not covered — and some of that *is*
branch-controlled: phpmd's `",".join(files)`, pmd's `-d <file>` per file, ruff's
spliced `*files`. They are safe because the core checked each of those paths
individually, against the named tool, before the helper reshaped them
(`model.Part.tools_that_read_its_arguments`, `batch_shell`), and neither joining
with a comma nor prefixing a flag can introduce a `cmd.exe` syntax character that
was not already there. So a helper argument built from branch data still needs
that question asked of it — do not read this as "helpers never touch branch
data". What is genuinely unchecked is what never came from the branch at all:
install paths, temp dirs, and a `path` read out of the config in force — jscpd's
`--output <tempdir>`, pmd's ruleset path, phpmd's phar. That is why the trade is
worth taking, but it is a trade and not a free win.

### `TimeoutExpired` carries no partial output at all on Windows

A killed tool's own words are the whole value of the timeout notice, and they do
not come back from the exception: POSIX hands over the partial reads, but on
Windows each pipe is drained by a thread sitting in a single `read()` that
returns only at EOF, so the buffer is still empty when the deadline passes.
`sensors/deadline.py` therefore reads the pipe *after* the kill — the second
`communicate()` from `subprocess`'s own docs — which is one answer for both
platforms and the fuller one, since anything printed between the deadline and
the kill is in it too. That read is bounded as well (`LAST_WORDS_TIMEOUT_SECONDS`):
something the kill could not reach can still hold the far end open, and waiting
on that forever is the hang the deadline exists to stop. When it does, the
original expiry stands, which is why `part_output._as_text` still takes bytes.
