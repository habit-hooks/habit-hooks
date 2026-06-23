# DECISIONS

Reversible design calls made by the autonomous loop while driving GOAL.md.
Each is labelled _agent decision_ per the working agreement.

## Phase 1 — Smell-key decoupling (TS, internal)

- **Routing keys become canonical smell keys.** _(agent decision)_ Each `Rule.id`
  and each `Violation.ruleId` is now a kebab-case smell key (e.g.
  `too-many-parameters`) instead of a tool-prefixed key (`eslint:max-params`).
  Tool-prefixed strings survive **only** as (a) the raw→smell translation tables
  owned by each wrap and (b) provenance written to `Violation.source`.

- **`Violation.source` added for provenance.** _(agent decision)_ Carries the raw
  tool key (`eslint:max-params`, `knip:classMembers`, `jscpd:duplication`,
  `comment:non-essential`). It is shown in the reporter's _Uncoached_ section so
  today's behaviour — surfacing the originating tool/rule for unknown findings —
  is preserved. Maps cleanly onto the future `Issue.details.source` (docs).

- **Unmapped raw keys pass through as their bare key.** _(agent decision)_ An
  eslint rule with no smell mapping (e.g. `no-console`) routes as `no-console`;
  an unknown knip issue type (e.g. `unlistedPeerDependencies`) routes under its
  bare key. No tool prefix leaks into the routing key; the finding still surfaces
  as uncoached with full provenance in `source`.

- **Catalogue content preserved verbatim.** _(agent decision)_ Titles,
  descriptions, and severities are copied unchanged from the old tool-keyed rules
  to guarantee output parity. Aligning titles with `docs/smell-vocabulary.md`
  (e.g. "Non-essential comment") is deferred as a separate content change.

- **`parse-error` stays a supplemental prompt** (no default `Rule`), exactly as
  the old `eslint:fatal` did — it has a tuned template but no catalogue entry.

## Phase 2 — Sensor contract + runner (leaf-only)

- **Phase 2 split into 2a + 2b.** *(agent decision)* 2a introduces the `Sensor` /
  `Issue` / `SensorContext` contract (`src/sensors/types.ts`) and a `SensorRunner`
  (`src/sensors/runner.ts`) that registers sensors, orders them by dependency, and
  merges issues — fully unit-tested in isolation, no pipeline integration yet. 2b
  makes the four wraps registered sensor plugins and wires them into `run()` with
  `Issue` <-> `Violation` conversion, preserving golden parity. The split keeps
  each commit small and reviewable, and de-risks the parity-sensitive integration.

- **`SensorRunner.run` returns `Issue[]`** per docs. *(agent decision)* Dependency
  ordering uses a stable topological sort (registration order preserved among
  ready sensors); unsatisfiable `dependsOn` smells and cycles throw at
  construction (startup error), per docs/sensors.md. Leaf-only is exercised by the
  preset; multi-sensor ordering/`ctx.deps` is implemented and tested with fakes but
  no multi sensor ships (out of scope).

- **2b integration: gated detect over all files, filter per smell afterwards.**
  *(agent decision)* `run()` runs each *active* preset sensor over the full
  discovered file set via `SensorRunner`, then `filterViolations` keeps a
  violation only if its smell's rule allows the file (uncoached smells with no
  rule are never file-filtered). A sensor is **active** iff at least one smell it
  `produces` has a rule resolving to a non-empty file set — reproducing the old
  "a tool runs iff its source has an active in-scope rule" gate, so disabling or
  empty-scoping a sensor's smells suppresses the whole tool (and its uncoached
  sibling smells), not just its coached output. This replaces the old per-source
  dispatch (eslint union + `filterEslintViolations`, group-by-file-set for the
  rest) and lets the sensor stage stay a pure detector — rule-scoped filtering is
  the seam the Phase 3 mapper will own. Verified parity: CLI golden byte-identical,
  full suite green, plus new gating tests. `src/eslint-runner.ts` deleted.

- **Known, accepted divergence: knip's coached findings now respect the baseline.**
  *(agent decision)* The old code never file-filtered knip output (knip runs
  whole-project and its violations bypassed filtering); the new uniform filter
  drops an `unused-class-member` finding for a **baseline-snoozed** file (that
  rule has `changedFilesOnly: false`, so scope can't drop it — only the baseline
  can). Unreachable by any existing test and not promised by the docs; treating a
  snoozed file as snoozed for every sensor is the more consistent behaviour
  (arguably a latent bugfix), so it is accepted.

## Phase 3 — Mapper smells config + fix resolution

- **3a: `smells` is the canonical config field; `rules` kept as a transitional
  alias.** *(agent decision)* The config now reads `smells` (smell-keyed, per
  docs/mapper.md) and still accepts `rules`; both merge with `smells` last so it
  wins on conflict. Default and canonical configs use `smells`. This introduces
  the canonical field without a sweeping rename of every test fixture; removing
  the `rules` alias is a later cleanup. Added the `fix` field to the schema/`Rule`
  and threaded it through merge so the Phase 3b mapper can resolve it.

- **Fixed a latent Phase-1 miss: the repo's own `habit-hooks.config.js`** still
  keyed an override under the old `comment:non-essential`, which now matches no
  rule and would throw (`missing 'source'`) if habit-hooks ran on itself. Migrated
  it to `smells: { 'non-essential-comment': ... }`.

- **3b: the mapper is a standalone, tested module (`src/mapper/mapper.ts`),
  integrated in Phase 4.** *(agent decision)* `mapIssues` groups the bag by smell
  and resolves each group to one `GuideAction` (severity + a `Fix`), with leftover
  smells in an uncoached bucket. `resolveFix` implements the chain — explicit
  `fix` setting, then `<smell>.md` (prompt), then a `<smell>` script (command),
  else uncoached — looking up override dir before packaged, and throwing a config
  error when an explicit `fix` names a missing file. Like the Phase 2a runner, it
  ships tested-but-unwired; Phase 4 builds the Nunjucks guide that consumes
  `GuideAction[]` and retires the reporter. (knip flags the output types as unused
  until then — expected.)

## Phase 4 — Nunjucks guide

- **4a: Nunjucks render + guide module (`src/guide/`), tested then integrated in
  4b.** *(agent decision)* `render.ts` builds a Nunjucks `Environment`
  (autoescape off — output is agent-facing markdown, not HTML; a `FileSystemLoader`
  over the override+packaged dirs lets templates `{% include %}` partials).
  `guide.ts` renders each `GuideAction`'s template against `{ smell, issues }`,
  lists the uncoached bucket, and computes the exit code (an `enforced` smell with
  any issue -> exit 1; uncoached never escalates). Per-smell grouping over
  multiple issues is proven with the `groupby("details.file")` filter (dot-paths
  work). Command fixes render nothing (out of scope). Reviewer's Phase-4 seam — a
  `routingFor` that folds in the supplemental seeds (e.g. `parse-error` at
  `enforced`) — is handled in 4b's runner wiring as `rule ?? lookupPrompt(smell)`.

- **4b: `run()` is now sensor -> mapper -> guide; the reporter is retired.**
  *(agent decision)* `run()` detects via sensors, filters per smell, converts to
  the `Issue` bag, maps to `GuideAction[]` (routing = merged rule ?? `lookupPrompt`
  so `parse-error` keeps `enforced`), and renders with the guide. `src/reporter.ts`
  and its test are deleted. The guide composes each section — `❌ {title}` /
  description / the prompt template / an issue list — so the output stays close to
  the old reporter format (titles, `file:line - message`, banner all preserved),
  keeping the substring-based integration tests green. Two changes are intentional
  new snapshots: section **order** now follows issue arrival (sensor order) rather
  than catalogue order, and the per-rule "(N more …)" cap is gone (templates list
  all issues). `oversized-function` ships a `.issues.njk` that groups by file —
  the real per-smell grouping the DoD asks for. Also fixed a second latent Phase-1
  miss: `packaged-dir.ts` probed the renamed `eslint-max-params.md` (worked only
  via the src fallback); now probes `too-many-parameters.md`. `.njk` partials are
  added to the published `files`.

- **4b fix: a routed smell with no tuned template falls back to `uncoached.md`,
  not the uncoached bucket.** *(agent decision)* Reviewer found an exit-code
  regression: seven enabled `enforced` smells ship no `<smell>.md`, so they were
  dropping to the uncoached bucket (exit 0), whereas the old reporter exited 1 for
  any enforced smell with a violation (docs/guide.md: "enforced smell with an
  unresolved issue -> 1"). Fix: a smell that **has routing** (known severity from
  config or catalogue) always becomes an action — its `<smell>.md` if present,
  else the generic `uncoached.md` body — keeping its severity so it renders as a
  section and escalates the exit. Only a smell with **no routing at all** (truly
  unknown, e.g. eslint `no-console`) goes to the uncoached bucket (never
  escalates). Matches the old reporter exactly. Guarded by a runner test isolating
  an enforced-but-untemplated smell (`loose-equality` -> exit 1).

## Phase 5 — Declarative adapter + Python preset

- **De-risk passed (validated in code).** *(agent decision)* Captured live
  `ruff --output-format=json` (flat array) and live `eslint -f json` (nested
  `messages[]` per file); `src/sensors/adapter.ts extractIssues` handles both via
  the two-level `group`/`items`/`fields`/`map` model — `adapter.test.ts` pins both
  shapes. The model expresses the two toolchains, so the preset is built on it.

- **`declarativeSensor` runs a JSON-emitting tool as a leaf sensor.** Splits the
  `command` on whitespace, expands `${files}`, runs it, parses stdout JSON, and
  extracts. Spawn failure -> stderr notice + zero issues (sensor contract).

- **Python preset (`src/sensors/python-preset.ts`): ruff + jscpd + deptry.**
  ruff `C901/PLR0913/PLR0915/F841` -> `high-complexity/too-many-parameters/
  oversized-function/unused-variable` per the GOAL table; jscpd reuses the shared
  `checkLeafSensor` for `duplicated-code` on `.py`; deptry runs
  `deptry . --json-output /dev/stdout` (flat array) and maps `DEP002` ->
  `unused-dependency`.

- **Agent decisions on the mapping:** added ruff `F401` -> **`unused-import`** (a
  new general smell — cheap and useful, per the GOAL's allowance). **Deferred
  `oversized-file` for Python** — no clean ruff rule (GOAL says best-effort or
  defer). deptry's `/dev/stdout` JSON is POSIX-only, fine for the Linux e2e.

- **Added ruff `BLE001` -> `swallowed-exception` (new smell).** A broad `except`
  that catches and discards the error is a silent-failure risk and has no clean
  TypeScript twin, so `swallowed-exception` is the first catalogue smell to carry
  `source: 'ruff'` (added to `RuleSource` in `types.ts` and to config validation,
  mirroring how `knip` is a spec-driven source). Severity `suggested`: blind-except
  has legitimate top-level uses (a request handler, a worker loop), so it coaches
  rather than failing the run. Exercised only when ruff is on PATH, skipped on CI
  like the other Python sensors.

- The live-ruff preset test skips when ruff is not on PATH (CI without the Python
  toolchain) so the suite stays green everywhere; it runs in the provisioned env.

## Phase 6 — init language selection + e2e

- **Language selection wired into `run()`.** *(agent decision)* `config.language`
  (`typescript` | `python`, default typescript) drives both file discovery
  (`**/*.{ts,tsx,js,mjs,cjs}` vs `**/*.py`) and the active preset
  (`buildPresetSensors` vs `buildPythonPresetSensors`). The activeness gate keeps
  only that language's sensors running. `init` detects the language from a Python
  manifest (`pyproject.toml`/`setup.py`, else typescript) and writes it to the
  scaffolded config.

- **Catalogue gap fixed: added `unused-file`/`unused-export`/`unused-dependency`
  (per docs/smell-vocabulary.md) and the new `unused-import`.** *(agent decision)*
  These were vocabulary smells with no `defaultRules` entry, so the activeness
  gate marked deptry (whose only smell is `unused-dependency`) inactive and it
  never ran. Cataloguing them coaches the smells and lets their sensors activate.
  The catalogue moved to `src/config/catalogue.ts` (line budget); `changedFilesOnly`
  is now optional on `Rule` (defaults false) to keep the catalogue compact.

- **Whole-project artifacts bypass source-file filtering.** *(agent decision)*
  `filterViolations` now keeps a violation whose file is not a discovered source
  file — a project-level artifact like `pyproject.toml`/`package.json` reported by
  deptry/knip can't be source-file-scoped (it was being dropped, hiding
  unused-dependency).

- **deptry uses the temp-report pattern, not the stdout adapter.** *(agent
  decision)* `deptry --json-output /dev/stdout` writes nothing when stdout is a
  pipe (only the human report reaches stderr), so the deptry sensor writes JSON to
  a temp file and feeds it through the adapter's `extractIssues`.

- **Python e2e fixture** (`tests/fixtures/python-project`) exercises all six
  Python smells; `src/python-acceptance.test.ts` asserts the expected counts and
  exit 1 (skips without ruff+deptry). The fixture's `pyproject.toml` configures
  ruff `mccabe.max-complexity` (like the TS fixture configures ESLint) so `C901`
  fires — preset thresholds come from the consumer's tool config.

## Init onboarding & language-aware setup (post-GOAL hardening)

Follow-up work after the GOAL phases: a flaky-test fix plus a language-aware
`init` that actually onboards a Python project. Delivered as six reviewed
phases (PR #13). Each call below is an _agent decision_.

- **jscpd cleanup test asserts on an injected tmp-root, not global `/tmp`.**
  _(agent decision)_ `runJscpdWrap` takes an optional `tmpRoot` (default
  `os.tmpdir()`); the cleanup tests pass an isolated root and assert on it. The
  old test snapshotted the shared `os.tmpdir()` for `hh-jscpd-*` entries, so a
  concurrent jscpd run from another parallel test file leaked in and failed it —
  surfaced once the Python tests (which also shell out to jscpd) run with the
  toolchain installed. Production behaviour unchanged.

- **`init [language]`; report-only when the language is omitted.** _(agent
  decision)_ With no argument, `init` detects the language and prints a
  report-only message telling the user to re-run with it specified — it writes
  nothing. An explicit language is threaded through (no re-detect). We chose a
  positional arg + report-only over an interactive prompt deliberately: agents
  struggle with TTY prompts, and an explicit language keeps the choice
  deliberate. An unsupported language exits 2 before any side effect.

- **Python tools detected on `PATH`; install commands span two ecosystems.**
  _(agent decision)_ `ToolName` gains `ruff`/`deptry`; they're pip-installed so
  they're detected via a `PATH` scan (`isOnPath`), while eslint/knip/jscpd keep
  node_modules detection (a `DETECTION_KIND` map selects). ruff is "configured"
  via a ruff config file or a `[tool.ruff...]` section in `pyproject.toml`;
  deptry via `pyproject.toml` presence. `installCommandsFor` groups missing
  tools into a `pip install …` line and a `<pm> add -D …` line.

- **Recommended thresholds mirror across languages, from one source.** _(agent
  decision)_ The scaffolded `ruff.toml` sets `mccabe.max-complexity = 10` and
  `pylint.max-args = 3` to match the TS ESLint template (`complexity 10`,
  `max-params 3`), so "too complex" / "too many params" mean the same in both
  languages. `pylint.max-statements = 50` is the ruff-only analog for PLR0915.
  The templates _derive_ these from the same `RUFF_RECOMMENDED`/`JSCPD_RECOMMENDED`
  constants the drift checks use, and a test pins that a freshly-scaffolded
  config satisfies `missingKeys() === []` — templates and recommendations can't
  silently diverge.

- **Python onboarding skips npm-only steps.** _(agent decision)_ `init python`
  scaffolds `ruff.toml` + a Python-flavoured `.jscpd.json` (deptry needs no
  config — guidance only), skips the `package.json` script prompts (a Python
  project may have none), installs a pre-commit hook that runs `habit-hooks`
  directly (vs `<pm> run habit-hooks`), and pastes a language-aware agent
  snippet naming the language's tools.

- **Drift detection is additive; eslint stays advisory.** _(agent decision)_
  The completion report flags a recommended value only when its key is **absent**
  (a value the user intentionally tuned is never flagged). Checks are cheap — JSON
  parse for `.jscpd.json`, a text scan for ruff thresholds — with no TOML parser.
  ESLint's flat `.js` config can't be cheaply parsed, so it's surfaced as a soft
  advisory `Note:` that never flips "✅ Setup complete" to "incomplete" (otherwise
  every configured TS repo would read incomplete forever).

- **`--accept-recommendations` only auto-applies the mechanically-safe fixes.**
  _(agent decision)_ Instruct by default. The flag runs the install commands
  (via an injectable `CommandRunner` so tests never shell out) and **additively**
  merges absent recommended keys into Habit-Hooks-owned `.jscpd.json` (never
  overwriting a user value). It deliberately does **not** edit user-owned
  `ruff.toml`/`pyproject.toml` thresholds or eslint config — safe in-place
  TOML/JS editing needs a real parser, so those stay reported as manual steps
  even with the flag. A failed install is reported and never aborts the rest or
  changes the exit code. Lifting the ruff.toml boundary (needs a TOML library)
  is a deferred follow-up.

## Issue-wrapup loop (GOAL #27)

- **The `rules` config alias is deprecated, not yet removed.** _(agent decision,
  #21)_ Per the one-release migration plan, `rules` is still accepted and folded
  (with `smells` winning on conflict), but a run whose config uses `rules` now
  emits `RULES_DEPRECATION` on stderr (detected in `buildContext`, surfaced via
  `RunResult.stderr`). All internal test configs were migrated to `smells`; the
  only remaining `rules` usages are the tests that intentionally cover the alias
  and its precedence. **Scheduled follow-up:** a later issue removes the `rules`
  field from the schema/merge entirely (the hard removal).

- **File discovery lives in its own module.** _(agent decision, #8)_ `FILE_GLOBS`
  and `discoverFiles` moved out of `runner.ts` into `src/discover.ts`. `runner.ts`
  sat exactly at the `max-lines: 200` limit, and discovery is a distinct
  responsibility from orchestration; the move keeps runner under the cap and gives
  the `scope.exclude` knob a focused home. Reversible — it could be inlined back.

- **Auto-prune is a CLI side effect, not part of `run()`.** _(agent decision,
  #11)_ Auto-pruning fixed baseline entries mutates a checked-in file, so it
  lives outside `run()` (which stays a pure evaluator) in `runWithAutoPrune`,
  alongside the other baseline mutations in the command layer. It fires only when
  `run()` reports `scopeMode === 'all'` (a full-repo run); scoped runs are a
  guaranteed no-op. It runs a **baseline-free** full scan (a second `run()` with
  `applyBaseline: false`) so a sensor gated off by the baseline can't make a
  snoozed file look falsely clean, and shares one reaper (`reapBaseline`) with
  manual `baseline prune`. The pruned set is printed so the mutation is never
  silent. Reversible — auto-prune could move into `run()` or behind a flag.

- **Python `oversized-file` via a line-count leaf sensor, threshold text-scanned
  from config.** _(agent decision, #19)_ ruff 0.15 has no `C0302` port and
  **rejects an unknown `max-module-lines` key under `[tool.ruff]`** (verified:
  `unknown field max-module-lines`), so the locked decision's "ruff-config-style
  key in the consumer's ruff config" cannot live inside `[tool.ruff]`. The
  language-agnostic `lineCountSensor` emits `oversized-file` for files over the
  threshold; the threshold is read by a no-TOML-parser **text scan** for
  `max-module-lines = N` across the consumer's ruff config + `pyproject.toml`
  (default 200, matching the TS `max-lines`). Consumers set it in a ruff-ignored
  location such as `[tool.habit-hooks]` in `pyproject.toml`. It is **not** added
  to `RUFF_RECOMMENDED`/the init scaffold, because recommending the key inside a
  ruff table would break ruff. Reversible — a future ruff C0302 (or a TOML
  parser) could relocate the threshold.

- **Sensor failures travel on a `SensorSink`.** _(agent decision, #25)_ A
  spawn/timeout failure now **fails the run (exit 1)** instead of being a
  false-clean. Rather than thread two parallel arrays, sensors share a
  `SensorSink { notices; failures }` (`src/wrap/notices.ts`); `failures` records
  any sensor that could not run, and `run()` forces exit 1 when it is non-empty
  while every successful sensor's output still renders. The failure message stays
  in `notices` too, so display is unchanged. Reversible — the sink could collapse
  back to a bare notices array if the policy were reverted.

- **`needs-extraction` is a real multi sensor; replace-mode runs in the sensor
  stage.** _(agent decision, #17)_ The composite (`oversized-file` +
  `duplicated-code` in one file → `needs-extraction`, enforced) is a genuine
  multi sensor using `dependsOn`/`ctx.deps`; the mapper stays a pure single-smell
  function. The augment-vs-replace switch (`needsExtraction.replace`, default
  augment) is applied by `applyReplaceMode` in the sensor module, called from
  `detect()` on the merged bag before the mapper — so combination logic stays in
  the sensor layer. The composite is wired into the **TS preset only** for now,
  because on `main` the Python preset has no `oversized-file` producer (that is
  #19); `satisfiableSensors` drops a composite whose dependency producers were
  gated out, so a config that disables an input can't crash the run. The
  catalogue entry lives in `customRules` (source `custom`) to stay under the
  200-line cap.
- **Smell knowledge lives only in config; the sensor layer consumes it.** _(agent
  decision, #24)_ All tool/smell mappings moved to `src/config/tool-smells.ts`:
  the eslint raw→smell map, eslint/knip/jscpd/comment produces, and the ruff +
  deptry `AdapterSpec`s. The eslint/jscpd/comment data is **derived from the
  catalogue** (so adding a smell there auto-wires its translation and produces);
  knip's raw issue types and the supplemental `parse-error` (an eslint fatal with
  no catalogue rule) are the config literals. The runner, sensors, checks, and
  rules registry now import these instead of hardcoding — the acceptance grep is
  clean for non-test source. (Test files still pin concrete smell strings as
  behaviour assertions.) Adding a new eslint smell touches only `src/config/`
  (catalogue) + `src/cli/init/` (the scaffolded eslint config) — proved live by
  the `deep-nesting` smell (#26). Realizes the locked "spec from config" via
  config-derived constants rather than per-call DI, keeping the refactor low-risk.

- **`deep-nesting` (TS, ESLint `max-depth`) is #24's live demonstrator.** _(agent
  decision, #26)_ Added the smell touching only `src/config/catalogue.ts` (the
  rule, `source: eslint`, `sourceRuleId: max-depth`, severity **enforced** to
  mirror `high-complexity`) and `src/cli/init/templates/eslint-config.ts` (the
  scaffolded `max-depth: 4`). The eslint raw→smell translation and the preset's
  produces **auto-derived** from the catalogue with zero edits to the runner,
  sensors, checks, or rules registry — the proof that #24 worked. Python
  `deep-nesting` (ruff `PLR1702`) is **deferred**: it is preview/unstable, and we
  do not opt the default preset into ruff `--preview`. Reversible — Python can be
  enabled once PLR1702 stabilises or via an AST detector.
