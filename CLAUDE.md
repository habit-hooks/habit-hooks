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

### jscpd resolves a config's relative `path` against the config file, not cwd (agent decision)

When `jscpd --config <abs path>` loads `.jscpd.json`, its `path: ["src"]` resolves
relative to the config file's directory, so a plugin-shipped config scans nothing
in the consumer repo. `plugins/generic/sensors/jscpd.py` therefore reads `path`
out of the config and passes those as positional args (resolved against cwd),
keeping the config the single source for threshold/ignore/minLines/minTokens.

## Gotchas

### knip runs a gated second pass in production mode (issue #59)

`knipWrap` runs knip twice when — and only when — the consumer's knip
config marks production patterns with a trailing `!` (detected by
`knipConfigMarksProduction` in `knip-resolve.ts`). The default pass is
authoritative for everything (incl. unused devDependencies); the
`--production` pass contributes only dead-code findings
(`PRODUCTION_PASS_SOURCES` in `knip-merge.ts`), merged + deduped. This
catches code reached only by tests without losing devDep detection.
Gotchas: `--production` analyses NOTHING unless `!` is on BOTH `entry`
and `project` (a no-`!` config under `--production` silently reports
zero — so we never pass it there). Test files must be listed as
unmarked (non-production) `entry`, else knip 5 + a vitest config falsely
reports them as unused files. The merge intentionally keeps `knip:files`
from the production pass, so a wholly test-only production file can
surface as an unused file — that's the feature, not a bug.

### JSDoc nodes are not MultiLineCommentTrivia in ts-morph

`/** ... */` blocks are `SyntaxKind.JSDoc` (321) when attached to a
declaration, NOT `MultiLineCommentTrivia`. To find them, query both. See
`src/checks/comment-check.ts`.

### knip's `exports` field omits the bin path

`knip` exports only `.` and `./session`, so
`require.resolve('knip/bin/knip.js')` fails. The bundled-fallback resolver
in `src/checks/knip-wrap.ts` (`bundledKnipBin`) resolves `'knip'` (main
entry) and navigates up to `../bin/knip.js` instead. Consumer-detected
knip is found via `detectTool`, which walks `package.json#bin.knip` and
does not hit this hazard.

### knip needs `package.json` in cwd

Running knip in a directory without `package.json` exits 2 with a help
message. `knipWrap` skips silently when no `package.json` is present —
the user's project always has one, but our internal test temp dirs
often don't.

### knip 5 vs 6 — issue type drift

We no longer pin knip; the consumer's installed version drives what
fires. v5 emits `classMembers`; v6 dropped that key and surfaces unused
exports via `files` / `exports` / `dependencies` instead. We ship
coaching prompts for all four so either version is covered. If a future
knip introduces a new top-level issue key, the wrap surfaces it as an
uncoached violation (see `unknownKeysForIssue` in
`src/checks/knip-wrap.ts`); add a prompt to coach it.

### comment-check file discovery doesn't honour project ignores

`runner.discoverFiles` uses fast-glob with a hardcoded ignore set
(`node_modules`, `dist`, `coverage`). Only `comment-check` consumes that
list directly — the eslint, knip, and jscpd wraps delegate discovery to
their respective tools. Fixtures under `tests/fixtures/**` therefore get
swept by comment-check when you run `node dist/cli.js` against the repo
root, which is why a smoke run on our own source shows comment
violations from inside fixtures.

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

### Wrap shell-out semantics — failures sit in `result.warnings`

`src/wrap/shell.ts` never throws on spawn/timeout failure. A spawn
failure surfaces as `exitCode === -1` with the cause in `warnings`; a
non-zero exit from the tool itself comes back with the real `exitCode`
and an empty `warnings`. The helpers `isSpawnFailure` and
`spawnFailureWarning` in `src/wrap/notices.ts` separate the two so a
crashed tool produces a stderr notice (and zero violations) instead of
silently swallowing the run.

### jscpd `-n` (noSymlinks) is baked in

`jscpdWrap` always passes `-n`. A consumer with intentionally symlinked
source directories (monorepo `src/shared -> ../shared-lib`) silently
will not get duplication detection on the linked paths. Surface this if
a user reports missing jscpd hits on a symlinked tree.

### Bundled habit-hooks ESLint vs project-local ESLint disagree on type-position param names

Our bundled config flags an unused parameter in a type-only function
signature (e.g. `resolve: (_result: ShellResult) => void`); the
project's flat config does not. Underscoring the param satisfies both.
This bit us during Phase 1/2 — if a wrap introduces a new callback type
and the build trips on `no-unused-vars` for a positional name, prefix
with `_`.

### Tool config filename lists live in `src/detect/tool.ts`

`TOOL_CONFIG_FILENAMES` and `TOOL_PACKAGE_JSON_KEYS` are the single
source for tool config discovery. When you add a new tool, a new config
filename, or a new `package.json` key (e.g. `eslint.config.cjs`,
`knip.jsonc`), update those tables only — `detectTool` and every
caller flows through them. Individual wraps may keep their own narrower
lists for internal "has-config" checks, but those should mirror the
canonical set.

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
