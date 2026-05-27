# Changelog

## Unreleased (v2 wrap pivot)

### Pivot
- Habit Hooks now wraps the linters your project already runs. It stops shipping its own rule set and stops invoking eslint / knip / jscpd programmatically.
- Rules, thresholds, and ignores come from your `eslint.config.*`, `knip.json`, `.jscpd.json` (or the matching `package.json` keys). Habit Hooks contributes only the coaching prompts.
- The `sourceOptions` field on rule overrides is now ignored. Tune the underlying tool's config instead.

### Wraps
- `eslintWrap` shells out to the consumer's eslint (`--format json`), falls back to the bundled binary with a stderr notice when no project-local eslint is found.
- `knipWrap` shells out to the consumer's knip (`--reporter json --no-exit-code --include classMembers`), skips silently without a `package.json` or a knip config, falls back to the bundled binary with a notice.
- `jscpdWrap` shells out to the consumer's jscpd into a tmpdir, scopes results to the changed-files set, skips silently without a jscpd config, falls back to the bundled binary with a notice.
- All three surface tool failures as stderr notices (`habit-hooks: <tool> skipped ...`) and return zero violations rather than crashing the run.

### Kept
- `comment-check` still runs in-process via ts-morph — it is not a wrap target.
- File-level baseline, git-aware scope, the prompts loader, and the reporter are unchanged.

### Init
- `npx habit-hooks init` detects which of eslint / knip / jscpd are already installed and configured, scaffolds starter configs only for the missing pieces, and prints the package-manager install command for missing binaries.
- Prompts cover scripts (`habit-hooks`, `ci`), a pre-commit hook, and the bundled `habit-hooks-review` skill.
- Adds `--dry-run` — print every intended write without touching disk.

### Prompts
- New supplemental prompts: `knip:files`, `knip:exports`, `knip:dependencies`, `eslint:boundaries/dependencies`.
- New `uncoached.md` header explains how to add a custom prompt for any rule we don't yet coach.
- Reporter groups any rule without a coaching prompt under a single "Uncoached rules" section so consumers see them without us needing prior knowledge.

### Breaking
- `sourceOptions` on rule overrides is dropped (silently ignored). All rule values move to the underlying tool's native config.
- The bundled "default rule set" no longer drives behaviour. Habit Hooks fires the rules that your tool configs say to fire.
- `knip` is no longer version-pinned by habit-hooks; consumer's installed version determines available issue types.
- Coached knip and jscpd violation messages no longer prepend the rule title (the reporter already shows it in the section header). Messages now read e.g. `Foo.unused` and `duplicates path/to/file:1-7` instead of `Unused class member: classMembers: Foo.unused` and `Duplicated code: duplicates ...`.

### Internals
- `src/detect/tool.ts` is the single source for tool config filename / `package.json` key detection.
- `src/wrap/shell.ts` provides timeout-and-spawn-safe `runTool`; `src/wrap/notices.ts` centralises the fallback/skip stderr notice helpers.
- New `RunResult.stderr` field carries wrap notices through to the CLI.
