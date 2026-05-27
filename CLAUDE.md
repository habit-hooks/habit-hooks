# habit-hooks notes

## Gotchas

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
