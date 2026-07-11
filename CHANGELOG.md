# Changelog

## 1.0.3

### Changed
- **TypeScript plugin**: the bundled `eslint.config.mjs` / `knip.json` defaults no longer exempt test files (`*.test.ts` / `*.spec.ts` / `tests/**`) from size and complexity rules — test code is now held to the same thresholds as production code. knip `entry`/`project` also broadened to cover `.tsx` and `.spec.*` files (#75).
- **Generic plugin**: the bundled `.jscpd.json` no longer ignores `*.test.ts`, so duplication inside test files is now detected (#75).

### Internal
- The core mapper builds the Jinja environment once per finding render instead of once per markdown template.
- The repo dogfoods the Python plugin's recommended ruff structural thresholds (`C901` / `PLR0913` / `PLR0915`, complexity 10 / max-args 3) and enforces them in CI.

## 1.0.2

### Internal
- The core config loader uses `attrs` instead of `pydantic`, dropping the compiled `pydantic-core` (Rust) dependency so the core is pure Python — enabling fast, Rust-free Homebrew bottles.

## 1.0.1

### Fixes
- Bundled Python sensors (`line-count`, `jscpd`, `deptry`, `phpmd`) now invoke the interpreter via the new `${python}` placeholder (`sys.executable`) instead of a bare `python`, so they run on environments without `python` on `PATH` (stock macOS, clean CI, Homebrew installs).

### Packaging
- The npm `habit-hooks` package is now a deprecation shim pointing at the PyPI / Homebrew distributions.
- Added the Homebrew install path (`habit-hooks/tap/habit-hooks`); GitHub Actions pinned to Node 24-native versions.

## 1.0.0

### Packaging
- Default install is now **core + generic**; the four language plugins (`generic`/`python`/`typescript`/`php`) are installable dists discovered via the `habit_hooks.plugins` entry-point group. Language plugins beyond generic install as extras.
- All workspace packages publish to PyPI via trusted publishing, each in its own per-package GitHub environment, on a `v*` tag.

### Sensors & languages
- **Consumer-defined sensors** (#16): the `sensors` config map is now the single way sensors are assembled — built-in and custom alike. Each entry is one of three mutually exclusive modes: `use` (reference a bundled sensor by id — `eslint`/`comment`/`jscpd`/`knip`/`ruff`/`deptry`/`line-count`/`needs-extraction`), a **wrapper script** (`command` + `produces` printing bag JSON), or a **declarative adapter** (`command` + `produces` + `items`/`fields`/`group`/`map`). The sensor id is the map key; `dependsOn` wires multi sensors. See `docs/sensors.md`.
- **Authoritative `sensors` semantics**: when `sensors` is present it replaces the language preset entirely (no merge), so removing a built-in is just deleting its entry. When `sensors` is absent the preset is used and a deprecation warning is emitted — this implicit fallback is **removed in the 1.0.0 release**.
- **Consumer-defined languages** (#16): `language` accepts any string. The built-ins (`typescript`/`python`) keep their preset + default file globs; any other value relies on the open `files` discovery globs plus a `sensors` map. A non-built-in language with no `files` emits a warning and discovers no source files.
- A custom sensor must be declared as a pair — its `sensors.<id>` entry **and** a matching `smells.<smell>` entry (a custom smell needs `id` + `source: "custom"` + `severity`). New config validation rejects malformed sensor specs (mode mixing, missing required fields) and bad `files` globs.

## 0.2.0

### Highlights
- Habit Hooks is now a smell-agnostic, config-driven coach: a three-stage pipeline (sensor → mapper → guide) connected by a JSON bag. Sensors detect findings and translate them into a canonical, tool-independent **smell vocabulary**; the mapper routes each smell to a fix; the guide coaches the agent and sets the exit code.
- Two language presets ship out of the box — **TypeScript/JavaScript** (ESLint + knip + jscpd + a ts-morph comment scan) and **Python** (ruff + jscpd + deptry + a line-count sensor). No sensors run by default; `init` enables the preset for the project's language.
- The smell catalogue, language presets, and per-language tool config drive behaviour. Concrete smell knowledge lives only in config and the language initializers — the runner, mapper, sensors, and checks are smell-agnostic.

### CLI & config
- `habit-hooks` runs the configured sensors over a project, groups findings by smell, prints each smell's coaching, and sets the process exit code — non-zero when an enforced smell fires, zero on a clean run or suggested-only findings.
- Git-aware scope flags restrict a run to a change set: `--last <n>` (files changed in the last N commits), `--branch [name]` (vs a branch, default `scope.branchBase`), `--since <hash>` (since a commit), and `--all` (force every file). The four are mutually exclusive; the default scope and per-rule `changedFilesOnly` come from config. `--config <path>` points at an explicit config file; `--version` prints the version.
- `habit-hooks.config.{ts,js,mjs}` is intentionally small: per-smell/per-rule `include`/`exclude` globs, `severity` overrides, `disabled`, and `changedFilesOnly`; a `scope` block (`onlyChangedFiles`, `branchBase`); a `prompts` directory for custom/override coaching text; and `commentCheck` thresholds. All tool thresholds stay in the consumer's own eslint/knip/jscpd/ruff config.

### Wrap model & coaching
- Habit Hooks drives the consumer's **own** installed eslint / knip / jscpd, surfacing whatever rules and thresholds those configs define; it falls back to the bundled binaries only when the project has none. The coaching layer (why-it's-a-smell + how-to-fix) is what Habit Hooks adds on top.
- The bundled coaching prompts for the size/complexity smells are adapted from the refakts refactoring-quality system — keeping its analyse-first / anti-mechanical-fix structure — with the remaining prompts explaining why each smell matters rather than restating the threshold.
- knip 5 and 6 are both supported: the consumer's installed major version is auto-detected so v5's `classMembers` and v6's per-issue `files`/`exports`/`dependencies` shapes are each read correctly, and v6 no longer loses every knip check over a rejected flag.

### Smell catalogue
- A canonical, tool-independent catalogue (kebab-case keys, see `docs/smell-vocabulary.md`). `enforced` smells fail the run (exit 1); `suggested` smells coach but exit 0; the mapper config can override severity per project.
- Enforced size/complexity smells: `oversized-function`, `too-many-parameters`, `high-complexity`, `deep-nesting`, `oversized-file`.
- Enforced correctness smells: `unused-variable`, `loose-equality`, `var-declaration`, `non-const-binding`, `duplicate-import`, `redundant-type-annotation`, and the unused-code family from knip/deptry (`unused-file`, `unused-export`, `unused-dependency`, `unused-class-member`, `unused-import`).
- Suggested smells: `warning-comment`, `explicit-any`, `non-null-assertion`, `non-essential-comment`, `duplicated-code`.
- `needs-extraction` (enforced) is a **composite** smell; `parse-error` (enforced) is a supplemental smell for ESLint fatals with no catalogue rule.
- Each sensor owns its raw rule ID → smell translation; the mapper and prompts only ever key off the canonical smell, never the tool.

### Sensors & presets
- **TypeScript/JavaScript preset**: ESLint (size/complexity/correctness/TS smells + `parse-error`), knip (`unused-file`/`unused-export`/`unused-dependency`/`unused-class-member`), jscpd (`duplicated-code`), and an in-process ts-morph scan (`non-essential-comment`). `comment-check` still runs in-process via ts-morph — it is not a shell-out sensor.
- **Python preset**: ruff (`high-complexity`/`too-many-parameters`/`oversized-function`/`unused-variable`/`unused-import`), jscpd on `.py` (`duplicated-code`), deptry (`unused-dependency`), and a language-agnostic line-count sensor (`oversized-file`).
- Preset thresholds come from the consumer's own tool config (e.g. ESLint `max-lines`/`complexity`, ruff `mccabe.max-complexity`/`pylint.max-args`), not from Habit Hooks.
- **Composite sensors via `dependsOn`** (#17): a multi sensor declares the smells it consumes, receives their issues in `ctx.deps`, and emits a derived smell. `needs-extraction` fires when one file is both `oversized-file` **and** `duplicated-code`. It augments by default (all three smells show); `needsExtraction.replace: true` suppresses the two inputs so only `needs-extraction` remains. The augment-vs-replace switch runs in the sensor stage, keeping the mapper a pure single-smell function. Wired into the TS preset and the Python preset.
- **deep-nesting** (#26): new enforced TS smell via ESLint `max-depth`. Python `deep-nesting` (ruff `PLR1702`) is deferred while that rule is preview/unstable.
- **Python `oversized-file`** (#19): a language-agnostic line-count sensor emits it for files over a threshold (`max-module-lines`, default 200). ruff has no `C0302` port and rejects an unknown `max-module-lines` key under `[tool.ruff]`, so the threshold is read by a no-TOML-parser text scan of the consumer's ruff config + `pyproject.toml`; set it in a ruff-ignored location such as `[tool.habit-hooks]`.
- **`command` fix action** (#18): a smell's fix can be a script instead of a prompt. The guide runs the command once per smell that has issues, streams its output into that smell's section, and folds its exit code into the run's exit code.
- **Declarative adapter**: a tool that already emits JSON can be wired as a sensor by declaring how to read it (`group`/`items`/`fields`/`map`, up to two levels of array nesting) — no wrapper script needed. Anything it can't express falls back to a wrapper script.
- **Sensor failures fail the run** (#25): a sensor spawn/timeout failure now exits 1 (instead of a false-clean) while still rendering every successful sensor's output. Failures travel on a shared `SensorSink`; the failure notice is shown on stderr.

### Baseline, snooze & auto-prune
- A file-level baseline (snooze) is committed to the repo at `.habit-hooks-baseline.json`, so a whole team shares one snapshot of legacy violations. A snoozed file stays snoozed for every sensor only while it appears in the baseline, its last-commit hash matches, and its working tree is clean — touching the file re-arms every smell, so you cannot silently drift past snoozed violations.
- `habit-hooks baseline` subcommands manage it: `generate` (record current violations), `status` (list snoozed files and freshness), `snooze <files...>`, `forget <files...>`, and `prune` (drop stale/resolved entries).
- **Auto-prune of dead snooze entries** (#11): on a full-repo run, Habit Hooks re-scans baseline-free and reaps snooze entries whose file is present but no longer produces the smell, printing the pruned set. Scoped runs never mutate the baseline (a file can look clean only because its smell is outside the diff), so they are a guaranteed no-op. Auto-prune shares one reaper with the manual `baseline prune` command.
- A memoized, batched snooze index collapses the per-rule git spawns to O(1) status + O(files) memoized log calls.

### Init
- `habit-hooks init [language]` onboards a project for its language. With no argument it detects the language and prints a report-only message; an explicit language threads through with no re-detect, and an unsupported language exits 2 before any side effect.
- Detects which tools are already installed/configured and scaffolds starter configs only for the missing pieces: an ESLint flat config (TS) or `ruff.toml` + `.jscpd.json` (Python), with package-manager install commands spanning pip and node ecosystems.
- The scaffolded ESLint config writes tunable thresholds including `max-depth: 4` (deep-nesting) alongside the other size/complexity rules, and exempts test files from size rules. Test globs derive from a single shared exclude list.
- Recommended thresholds mirror across languages from one source (ESLint `complexity 10` / `max-params 3` ↔ ruff `mccabe.max-complexity 10` / `pylint.max-args 3`); a freshly-scaffolded config is pinned to satisfy the drift check.
- Drift detection is additive — a recommended value is flagged only when its key is absent, never when you've tuned it. `--accept-recommendations` runs the install commands and additively merges absent recommended keys into Habit-Hooks-owned config, never overwriting user values or editing user-owned `ruff.toml`/`pyproject.toml`/ESLint config.
- Prompts cover package.json scripts, a pre-commit hook, and the bundled `habit-hooks-review` skill. `--dry-run` prints every intended write without touching disk.

### Architecture
- **Config-driven, smell-agnostic** (#24): all tool/smell knowledge lives in `src/config/tool-smells.ts` — the ESLint raw→smell map, the eslint/knip/jscpd/comment `produces`, and the ruff + deptry adapter specs. ESLint/jscpd/comment data is **derived from the catalogue**, so adding a smell there auto-wires its translation and produces; the runner, sensors, checks, and rules registry import these instead of hardcoding any smell id. `deep-nesting` (#26) was added by touching only the catalogue and the init ESLint template — the live proof of #24.
- Single source for tool config discovery: `TOOL_CONFIG_FILENAMES` / `TOOL_PACKAGE_JSON_KEYS` in `src/detect/tool.ts`.
- A routed smell with no tuned `<smell>.md` template falls back to a generic `uncoached.md` body while keeping its severity; a truly unknown smell (no routing at all) goes to the uncoached bucket and never escalates the exit code.

### Breaking changes
- The bundled "default rule set" and programmatic tool pinning of the beta are gone. Behaviour is driven by the smell catalogue plus the consumer's own tool configs; `knip` is no longer version-pinned, so the consumer's installed version determines available issue types.
- The `rules` config field is **deprecated in favour of `smells`** (#21). `rules` is still accepted and folded in (with `smells` winning on conflict), but a config using it now emits a deprecation warning on stderr. Hard removal of `rules` is scheduled for a release after 0.2.0.
