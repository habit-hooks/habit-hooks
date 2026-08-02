# DECISIONS

Design calls for the `simplified` rewrite — a ground-up re-org to cut cruft (the
old single-package, TS-baked design was ~5.6k non-test LOC for behaviour that is
a few small pipes). Calls are _human requested_ (Ivett) unless noted.

- **The pipeline is composed commands** — `habit-sensors | habit-mapper` —
  carrying a JSON array of `{smell, language?, details}` findings. `habit-mapper`
  absorbs the old mapper **and** guide stages (route + render + exit). Snoozing
  and adapting are **sensors**, not separate stages.

- **Everything language/tool-specific lives in `plugins/<language>` and
  `plugins/generic`** — each a dir of `sensors/*.toml` specs and `guides/` files,
  contract-only. Generic owns the language-independent sensors (line-count →
  oversized-file, jscpd → duplicated-code). TS keeps eslint/knip/comment; Python
  keeps ruff/deptry.

- **A sensor is a single `.toml`** carrying `command` + `produces` (+ optional
  `language`/`dependsOn`/`files`). It just has to print the findings array; an
  adapter sensor maps a JSON-emitting tool with a `jq` transform in the command
  ([authoring-plugins.spec.md](authoring-plugins.spec.md)). One descriptor source,
  read statically — no `--describe` subprocess. _(Ivett's call over the agent's
  two-source proposal.)_

- **`.habit-hooks/` in a consumer holds overrides only** (Q1b) — project
  `config.toml` plus any sensor/guide it replaces. Defaults resolve from the
  package, so updating habit-hooks never clobbers tuning. Resolution is
  first-match across `.habit-hooks/<lang>` → `.habit-hooks/generic` →
  `plugins/<lang>` → `plugins/generic`.

- **`oversized-file` defaults to the generic line-count sensor; languages may
  override.** TS uses eslint's `max-lines` instead (disables `line-count` in its
  config, maps `max-lines`); Python keeps the generic sensor. The pattern for any
  generic-vs-language-native smell: generic default, language override.

- **No composite ships by default.** The composite mechanism (`dependsOn` +
  stdin) stays first-class in the contract, but `needs-extraction` was only ever a
  demonstrator — it moves to a demo project. Docs still cite it for the mechanism.

- **Config is TOML** (Q5).

- **The rebuild targets Python** — chosen over a TypeScript build (Python is more
  often present in polyglot dev tooling and avoids shipping binaries) and over a
  Go binary (zero-runtime + Windows, but adds release machinery).

- **Snooze keying: git by default, mtime fallback** — content-accurate without
  hashing every file; pluggable for free since snooze is a filter sensor.
  _(SUPERSEDED by issue-key snooze below — mtime/git keying is dropped.)_

- **Fixes run via configured runners, not direct execution** — only `.md` is
  rendered by default; `[runners]` maps a guide extension to a command, so no
  arbitrary execution ships out of the box.

## Pipeline redesign (2026-06, all Ivett's calls)

The sensor runner is a recursive **ETL pipeline**. These supersede the
earlier `dependsOn` / composite / augment-replace / snooze-keying notes above.
Pinned in [habit-sensors.spec.md](habit-sensors.spec.md).

- **Two roles, one interface (`findings → findings`).** A **sensor** senses (no
  finding input) over scoped files. A **transformer** takes the whole findings
  array on stdin and returns a new one, with one invariant: **it must pass
  through everything it does not handle.** That single rule replaces `dependsOn`,
  augment/replace modes, shadow-on-re-emit, the `output` sink, topological
  ordering, and the `["*"]` wildcard — all deleted.

- **Recursive concat-then-transform.** A node = `transformers ∘ concat(child
  sensors)`, evaluated in listed order; it composes recursively, so the root
  (`habit-sensors`) and each plugin are the same shape. Transformer order is just
  list order; `snooze` is a root transformer because that is where it sees every
  finding.

- **A plugin is a bundle, not a language** — `sensors/` + `transformers/` +
  `guides/` + `config.toml`. `plugins` (renamed from `languages`) lists the
  active ones, `generic` explicit so it can be dropped. A plugin **declares** its
  `language` in config (generic declares none); the runner stamps it. Because
  language is declared, not the plugin name, **multiple plugins can share a
  language** (e.g. `eslint` and `biome`, both `typescript`).

- **The `plugins` list is ordered = lookup priority.** It is the concat order
  here and the guide-resolution order in the mapper: walk plugins in order, stop
  at the first that handles `(smell, language)`, then fall back to `generic`.
  (Reverses the earlier "derive language from the plugin dir name" Phase 0
  resolution — language is now a declared plugin attribute.)

- **Finding contract gains a top-level `issues`.** `{smell, language?, details,
  issues}` where `details` is the smell-level bag and `issues` is a list of
  `{key, details}` — each issue carrying its own `details` bag, symmetric with
  the finding's. (Was `details.issues` of flat bags.)

- **Snooze is issue-key based, not mtime.** `snooze` drops issues whose `key` is
  in the checked-in index (keyed on `key` alone; `key` defaults to the filename,
  so the common case snoozes a whole file). The sensor chooses the key, so
  lapse-on-change becomes a key-design choice (embed content to auto-lapse), not
  a core feature. `--prune` drops keys absent from the latest run.
  _(AMENDED by "Lapse-on-change is a second transformer" below — the index is
  still keyed on `key` alone, but lapse-on-change is available from the core.)_

- **`produces` dropped from sensor specs** — it only fed ordering/activation;
  ordering is gone, so sensors always run.

- **One `config.toml` for both stages** — the runner reads
  `plugins`/`transformers`/`sensors`/`files`/`scope`; the mapper reads
  `smells`/`runners`. They ignore each other's sections; no physical split.

- **Guide fixers are part of the plugin bundle.** The bare core renders only
  `.md` guide templates; nothing executes otherwise. A plugin ships its own
  `[runners]` in its `config.toml` (resolved through the override chain), mapping
  a guide extension to a command, so a plugin can run its **own
  language-specific fixers** out of the box — e.g. the python plugin maps
  `py = "python"` and its `guides/<smell>.py` scripts run. A project can add or
  override a runner the same way. No arbitrary execution ships unless a plugin or
  the project opts in.

- **Every documented config key has a consumer, or is gone (#87).** Four keys the
  docs described as working were read by nothing. Dispositions:
  - **Plugin `[runners]` — implemented.** `config.load_config` now merges each
    active plugin's `[runners]` under the project's, the way `files` is merged
    (earlier plugin wins a key, project wins over all). This is what the decision
    above always promised; the merge finally exists, so a third-party plugin
    shipping `guides/<smell>.<ext>` plus a `[runners]` entry has its fixer run.
  - **`[sensors.<name>] files` (and a sensor spec's own `files`) — implemented as
    a narrowing.** The `Part` carries the sensor's globs; `Execution` filters the
    already-resolved `scope.files` to that subset for the sensor alone (shared
    `scope.matching`). This is **not** a second scope mechanism: the scope is
    still derived once in `resolve_scope`, and a sensor's `files` can only select
    a subset of what it picked — never widen, never re-derive. `args` and `files`
    override the sensor spec's default wholesale, through one `_sensor_setting`.
  - **`[sensors.<name>] command` / `language`, and a sensor spec's own
    `language` — deleted.** A project wanting a different command or stamped
    language replaces the whole `sensors/<name>.toml` via the override chain, and
    a sensor's language is inherited from its plugin's `config.toml`; per-sensor
    copies read by nothing were removed from `SensorOverride` and the docs.
  - **`SmellOverride.title` — deleted.** Surfaced by the field-has-a-consumer
    test: `title` (and a `description` shown alongside it in an example) routed
    nothing — `severity` does — so both left the docs and `title` left the
    dataclass. `args` was added to the `[sensors.<name>]` doc tables, which had
    omitted the one per-sensor override that always worked.

  The guard against the class recurring is #102 (reject unknown keys); this
  cleared the existing instances. `tests/test_config.py` asserts, parameterised
  over `SensorOverride`/`SmellOverride` fields, that each has a consumer, so a
  future dead field fails the build.

- **Scope surface = main's, restored, plus `--file`** — `--all`, `--branch
  [base]`, `--last <n>`, `--since <ref>`, `--file <path>`, `--config <path>`;
  default from `[scope]` (`changedOnly` → uncommitted; else `autoBranchOffMain`
  → vs base unless on `mainBranch`; else all).

- **Specs build fixture plugins in temp** via the `.habit-hooks/<plugin>`
  override chain (no plugins ship in this repo long-term); the harness `📄 @<src>`
  copy gains recursive-directory support for larger fixtures.

## Deferred (migrated from the now-deleted open_questions.md)

- **Plugins as separately-installable packages.** Agreed direction: plugins
  eventually ship independently (`@habit-hooks/typescript`, etc.) for independent
  release + community contribution. For now the in-repo `plugins/<plugin>` model
  stands; the package split is a later, additive step.
- **`init`'s new shape.** The old ~1.3k-line scaffolder is slated for deletion in
  favour of copying override templates into `.habit-hooks/`. Revisit once its
  much smaller shape is decided.

The three earlier design gaps (sensor-command bin resolution, conditional adapter
mapping, config validation) are resolved and recorded above / in
[checklist.md](checklist.md).

## Tests are not exempt from quality tooling (2026-07, issue #75)

- **Test code is production code; never exempt tests from linting / complexity /
  duplication tooling.** The only legal test-specific carve-out is treating test
  files as **entry points during dead-code detection** (they are roots, not dead
  code), so a symbol used only by tests is not falsely flagged as unused and the
  test file itself is not reported as an unused file.
- **Removed exemptions:** the typescript plugin's `eslint.config.mjs` no longer
  turns `max-lines` / `max-lines-per-function` off for `*.test.ts` / `*.spec.ts` /
  `tests/**` — every size/complexity rule now applies to test `.ts` **and** `.tsx`
  (the base block already scopes `["**/*.ts", "**/*.tsx"]`). The generic plugin's
  `.jscpd.json` (and the repo-root dogfood copy) no longer ignore `**/*.test.ts`,
  so duplication in test files is detected.
- **knip (kept, extended):** test files stay listed as `entry` — the legal
  dead-code exemption above. Entry globs were widened to `.tsx` and `.spec`
  variants so co-located React/component tests are treated as roots too (else knip
  reports them as unused files). `ignore: ["tests/**"]` is **kept deliberately**:
  narrowing it to surface unused helpers in a separate `tests/` tree would require
  pulling `tests/**` into `project` scope and enumerating every test-file
  convention as an entry, trading a small gain for real false-positive churn
  across diverse consumer layouts. Co-located tests under `src/` are already in
  scope, so their unused helpers are already surfaced.
- **Deleted** the stale `prompts/build-habit-hooks-overnight.md` overnight
  build-scaffold prompt, which had documented the (now-removed) test exemption as
  intended behaviour.

## Lapse-on-change is a second transformer (2026-08, issue #80, Ivett's call)

- **The default `snooze` does not change, and stays the default.** A project
  upgrading from 1.0.x must never find its snoozes re-arming by themselves; a
  recorded snooze still lasts until someone takes the key out of the index.
- **`snooze-until-changed` is the opt-in ratchet.** Same index, same key
  semantics, but an exemption holds only while its file is unchanged against
  `[scope] branchBase`. That is what the npm predecessor's `snoozedAtCommit`
  gave, and what makes a baseline a ratchet rather than a permanent exemption
  list: debt is exempt until you are editing the file anyway. It ships from the
  core next to `snooze`, so opting in is one word in `transformers`.
- **Why not just design better keys** (the amended decision above): no sensor
  ever encoded content in a key, so the ratchet simply vanished. Keeping the
  index keyed on `key` alone and moving the question into the drop decision
  leaves the index format and `--prune` untouched.
- **An issue is anchored to `details.file`, falling back to `key`.** A sensor
  keys by whatever groups issues best — `deptry` by module, `knip` by export —
  so the key is not always a path; all eight shipped sensors carry
  `details.file`.
- **Measured from the merge base of `branchBase` and `HEAD`**, not the base ref's
  tip, so a branch is only ever judged on the debt it touched itself; work landed
  on the base ref afterwards lapses nothing.
- **A path git cannot place means "unchanged"; a ref it cannot resolve is fatal.**
  Untracked files and projects without a repository keep their snoozes — the
  opposite would re-arm a whole index on an answer git never gave. But a
  `branchBase` missing from a real repository (a shallow CI checkout, a `master`
  trunk) would answer "unchanged" for *every* file and make every snooze
  permanent with no signal — the exact silent green #80 was filed about — so it
  exits non-zero instead. `execution._transform` turns that into a failed run
  that keeps the findings untransformed.

## Finding paths are anchored at the sensor boundary (2026-08, issue #79, agent decision)

- **Every `details.file` is re-expressed relative to the project as a sensor's
  findings enter the run** — `sensors/finding_paths.py`, called from
  `Execution.run_sensor` — rather than by each sensor. `ruff`, `eslint` and
  `ts-morph` report absolute paths, so a snooze index recorded from them matched
  nothing on a teammate's checkout or in CI: machine-specific keys, silently
  evaporating a whole team's baseline now that snooze runs by default. Anchoring
  in one place is what makes a sensor obey a convention it never heard of, which
  is the difference between a framework invariant and a per-project patch.
- **A `key` is anchored by the same rule as the file**, whatever spelling the
  sensor used (`./src/a.py`, an absolute path, a redundant `src/../src`). No
  special case is needed for the carve-out: a key that is not a path (`deptry`
  keys by module, `knip` by export name) has nothing to resolve and comes back
  byte for byte. Tying the rewrite to "the key equals the file" instead — the
  first attempt — left an oddly-spelled key un-anchored *and* split one sensor
  key into two, which hid the aliasing below.
- **A path that cannot be anchored fails its sensor** — an absolute path outside
  the project, or a relative one escaping it. It raises `SensorError`, so it
  surfaces as a notice and a failed run through the existing contract, and that
  sensor's findings are dropped rather than keyed on a guess that would match
  nothing anywhere.
- **A key that is one of its own files while covering others too fails the run**,
  but keeps the findings: they are sound, it is snoozing them that is not. It goes through the
  notice channel — the run's only "somebody has to look at this" channel — since
  a warning nobody must act on is exactly how #79 stayed invisible for so long.
  Non-path keys are exempt by the rule above, so `knip` reporting the same unused
  export name in two files fails nobody's run.
- **Malformed output fails by name, never as a traceback.** An issue that is not
  an object, a `details` that is not one, an `issues` that is not a list: this
  boundary reads programs nobody here wrote, so it must degrade like a broken
  sensor rather than escape `pool.map` and out of `main`.
- **No existence check.** Rejecting a path that does not resolve to a file (the
  issue's option 2) would fail runs over deleted paths, which git-scoped runs
  still hand to sensors today (#81), so anchoring stays lexical. Two shapes
  therefore stay undetectable, and the docs say so rather than implying
  otherwise: a sensor reporting *identical* wrong paths for two files (they look
  like one file), and a key matching none of its files (indistinguishable from a
  deliberate grouping key). The shipped `jscpd` sensor was checked against
  jscpd 4 and reports cwd-relative paths in every invocation shape, so the
  reported case comes from a project-local sensor, not from ours.
- **Cross-sensor aliasing is out of scope.** `aliasing_notices` runs per sensor,
  but `snooze.py` stores bare, un-namespaced keys for the whole run — so two
  *different* sensors emitting one key for different files (a `deptry` module and
  a `knip` export both called `requests`) still alias with no notice. Fixing that
  means namespacing the index (`<sensor>#<key>` or `<smell>#<key>`), which is an
  index-format migration, not a boundary change.
- **Migration:** an index entry recorded before this change from an absolute-path
  sensor no longer matches, so its issues come back. Re-snooze once
  (`habit-sensors --all | habit-snooze --snooze`), then `--prune` drops the stale
  absolute keys.

## The scope is narrowed once, for every mode (2026-08, issue #81, agent decisions)

- **Both narrowings live in `resolve_scope`, not in the sensors.** Whatever mode
  picked the paths, a path the work tree no longer has is dropped and what
  survives must match `[files]`. Every git mode used to hand `git diff
  --name-only` straight through, so a deleted path reached `line-count.py`
  (`FileNotFoundError`, exit 1, empty stdout — read as a clean run, #78) and a
  lockfile bump produced `oversized-file: pnpm-lock.yaml`. Fixing it per sensor
  would mean every sensor, in every plugin, re-implementing the same two guards,
  and any third-party sensor getting it wrong by not knowing they existed.
- **`[files]` applies to `--file` too.** One setting answers "what does this
  project consider source", or it answers nothing: an editor hook firing on a
  lockfile edit must not score the lockfile. The cost is that `--file` on a path
  outside `files` scans nothing — the same answer `--all` gives it.
- **Scope now measures from the merge base, like `changed_files` does.** Two-dot
  `git diff <base>` compares the base ref's *tip* to the work tree, so a branch
  was scoped in files somebody else changed on the base after it forked — the
  gate failing on debt this branch never touched. The consequence differed from
  the same reading in snooze (there it lapsed an exemption; here it merely lints
  extra files), but the question is identical — "what has this branch changed?" —
  and two answers to one question is how #80 and #81 became separate bugs. One
  reading now serves both, and `[scope] branchBase` means the same thing wherever
  it is read.
- **A base ref a real repository cannot resolve fails the run**, the same
  distinction `changed_files._comparison_point` draws, by the same
  `git rev-parse --verify --quiet <ref>^{commit}` exit codes. Git answers a ref
  it never heard of with an empty diff, so a typo'd `branchBase`, or a shallow CI
  checkout without the base, scanned *nothing* and reported every sensor clean.
  "No repository" still outranks it — that is the existing, clear `SystemExit`,
  and it is checked first. The message names the ref and whatever chose it
  (`[scope] branchBase`, `--branch`, `--since`, `--last`), because the remedy
  differs per mode.
- **`files` is the one root key a plugin supplies a default for**, and the merge
  is a union across the active plugins in `plugins` order, deduped, with the
  project's own list replacing it wholesale (replace-on-override, as
  `transformers` and `[sensors.*] args` already are). Union rather than
  first-wins because a polyglot project's source is the sum of what its plugins
  call source; order is kept because pathspec reads the list in order, so a later
  pattern can negate an earlier one. A plugin that declares no `files`
  (`generic`) states *no opinion*, not "everything" — otherwise every union would
  be everything and the default would be worthless. The three shipped language
  plugins had declared `files` since they were written, and nothing ever read the
  key.
- **Supersedes the "No existence check" note above (#79)**, which argued that
  anchoring must stay lexical because git-scoped runs hand deleted paths to
  sensors. They no longer do. Anchoring stays lexical for the reason that
  outlived that one: a sensor may report a path the scope never handed it, and a
  boundary that reads somebody else's program should resolve names rather than
  ask the filesystem.
