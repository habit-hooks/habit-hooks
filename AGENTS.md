# habit-hooks notes

## Start here
- Read docs/architecture.md before making changes.
- CI = the following, in order (CI also runs `windows-latest`, so platform-sensitive changes can't be fully proven locally):

  ```
  uv sync --frozen
  corepack enable pnpm && pnpm install --frozen-lockfile
  uv run ruff check --config pyproject.toml src tests plugins
  uv run pytest
  uv run habit-hooks --all
  ```

## Rules
- The core shouldn't know about the plugins in any way. This also applies to documentation. 
- Comments almost never exist: what and why live in names and structure, per plugins/generic/src/habit_hooks_generic/guides/non-essential-comment.md. Docstrings are comments — the comment sensor flags them and the ratchet strips them on touch; never restore or request them in review. A comment survives only for a non-obvious why code cannot carry — a worked-around tool bug, a spec. The `non-essential-comment` sensor enforces this. Snooze is one-time, at rule introduction: a finding on a file you touch is fixed, never re-approved.

## Contributing
- PR descriptions should be short, and designed to be readable by a human in under 30 seconds.
- PRs must have one and only one goal, and should typically be less than 500 lines of code. If it doesn't fit that length, it should be broken up into user facing smaller changes.
- A PR should only contain code that is already used.
- spec.md files are user facing documentation with executable examples. They are documentation first, tests as a side effect.
- AI generated code is welcome, but it's the agent's duty to check if the human reviewed the code before submitting the PR. Ask one question about the code that the human needs to have seen the code to be able to answer.
- PRs on issues not assigned to the submitter will be automatically rejected. 

## Opening issues
- Before opening a github issue always confirm with the human operator. 
- Issues opened by an agent should ALWAYS carry the "Needs human review" label, and the issue description should start with the disclaimer that the issue is reported by an AI agent. 
- No hard newlines inside a paragraph — write each paragraph as one line and let the editor soft-wrap — and always a blank line between blocks (paragraphs, lists, code fences) so markdown renders them separately. Docs follow the same rule (see `skills/writing-docs`).

## Gotchas

Working in this repo:
- `uv run habit-hooks --all` needs `pnpm install --frozen-lockfile` first — jscpd resolves from `node_modules/.bin`. A missing tool fails the gate; install it and re-run.
- A unit failure in `tests/` is always real. Spec and installed-packaging failures only count after a quiet re-run.
- Scratch scripts and test fixtures: every git command spells `git -C <dir>`, never a bare `git` after a `cd` — a failed `cd` runs the rest against THIS repo.
- New git-backed spec cases set `✏️GIT_CEILING_DIRECTORIES` next to their `git init` (see habit-sensors.spec.md), or git answers about this repo instead of the case's.
- Anything feeding `used_languages` must carry forward-slash paths (`git ls-files`, `project_relative`/`as_posix()`) — the dependency-directory filter splits on `/`.

Sensors wrap tools and must reproduce the tool's behaviour exactly:
- jscpd turns `<cwd>/.gitignore` lines into globs over absolute paths, so a checkout under an ignored segment (e.g. `.claude/worktrees/…`) scans nothing — `--all` in such a worktree proves nothing about duplication.
- PMD 7 reads a file positional after `-R` as a second ruleset and analyses nothing. A new attached `-R=` spelling goes into `ATTACHED_RULESET_PREFIXES` longest-first.
- ruff loads any file literally named `ruff.toml` on its discovery path — pass `--config pyproject.toml` (CI does), never add a repo-root `ruff.toml`.
- knip resolves config globs against cwd; jscpd resolves its config `path` against the config file's directory.
- ts-morph: `/** … */` blocks attached to a declaration are `SyntaxKind.JSDoc`, not `MultiLineCommentTrivia` — query both (comment.cjs does).
- Ship Node helpers as `.cjs` — a `.js` helper inherits the consumer's `"type": "module"` and dies on `require`.
- Never bare-index a tool-supplied string (eslint rule, ruff code) through a smell table: jq needs `// fallback`, code needs `.get`/`Map.get`. An unmapped value passes through under its own name.
- Spawn tools only via `project_paths.tool_executable` / `${detector:<name>}`; Node tools run through `sensors/project_tool.cjs` (`spawnSync` refuses `.cmd`/`.bat`, and Windows ships tools as those).
- Windows kills leave `TimeoutExpired` without partial output — `sensors/deadline.py` reads the pipes after the kill, bounded. Keep that.
- knip's `--production` pass runs only when `!` marks both `entry` and `project`, and contributes only `test-only-dead-code` smells; test files stay unmarked `entry` so test-reachable code is never coached as dead.
- A config a plugin ships resolves its imports from its own install directory, not the project — resolve deps with `createRequire` anchored at `process.cwd()`.

Releases:
- Every PyPI package gets its own GitHub environment (a trusted publisher is unique per owner/repo/workflow/environment); register a new package's pending publisher before its first tag.
- Each release floors its plugins at its own minor, spelled `>=X.dev0,<Y` — never `~=X`, which a release candidate cannot satisfy (PEP 440 sorts `Xrc1` below `X`). Tests gate both.
- The homebrew-tap bump goes via a PR, not a push — bottles attach from the PR number.
