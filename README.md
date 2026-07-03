# habit-hooks

Stop reciting software engineering literature to your AI agent.

Turn best practice advice into AI habits, and make it write code like this:

![write_code_like_this.png](write_code_like_this.png)

## What it is

AI coding agents frequently ignore long rule documents. Asking them to hold on to an entire book's worth of
coding advice is at best futile, at worst makes the agent's performance worse by polluting the context window.

Humans don't need to hold the same information in their head because humans can form habits through repetition.
However, AI agents can't do this.

Human habits form when an easy-to-detect cue triggers a complex sequence of actions with the desired effect.
This is the inspiration for habit hooks.

Linters provide a deterministic metric, but Goodhart's law postulates that a metric ceases to be a good metric if
it becomes a target. AI agents are very good at gaming these metrics when they are only provided the metric.

Habit hooks runs your linters to create the trigger, but instead of providing only the metric, it gives actionable
advice on how to fix the issue. This creates AI behaviour that looks like human habits, and has similar effects.

The use of habit hooks:
- Increases code quality
- Improves AI performance ensuring that the AI always starts with good code quality
- Reduces token usage, since good quality code also means the AI doesn't need to read as much context to complete the task.

## How it works

Habit hooks is two small command-line tools joined by a Unix pipe. Between them flows a JSON array of **findings**.

```
habit-sensors <scope flags> | habit-mapper
```

- **`habit-sensors`** finds the smells. It runs the configured detectors over the files in scope and emits a
  findings array on stdout.
- **`habit-mapper`** acts on them. It reads the findings on stdin, groups them by smell, renders each smell's
  coaching guide, and sets the exit code from each smell's severity (`enforced` fails the run with exit 1,
  `suggested` coaches but exits 0).

`habit-hooks` is just the composition of the two — `habit-sensors $ARGS | habit-mapper` — so the same arguments
scope the run and the same findings drive the coaching. Because the stages talk only through findings on a pipe,
each can be run, tested, or replaced on its own.

Each sensor translates a tool's raw rule IDs into a tool-independent **smell key** (`max-params`, `PLR0913`, … all
become `too-many-parameters`), and everything downstream routes on that key alone. The mapper picks a guide by
smell, never by which tool reported it.

## Install

habit-hooks is a Python package (requires Python 3.11+). Install it with `uv`, `pip`, or Homebrew:

```sh
uv tool install habit-hooks
# or
uvx habit-hooks
# or
pip install habit-hooks
# or
brew install habit-hooks/tap/habit-hooks
```

This gives you **core plus the generic (language-agnostic) plugin** and installs four commands on your `PATH`:
`habit-hooks`, `habit-sensors`, `habit-mapper`, and `habit-snooze`.

The three language plugins are **opt-in** via extras:

```sh
uv tool install "habit-hooks[python]"       # adds the python plugin
uv tool install "habit-hooks[typescript]"   # adds the typescript plugin
uv tool install "habit-hooks[php]"          # adds the php plugin
uv tool install "habit-hooks[all]"          # adds all three
```

To pick language plugins per project without a global install, run from the extra with `uvx` (uv caches it):

```sh
uvx --from "habit-hooks[typescript]" habit-hooks
```

Alternatively, vendor a plugin's files under `.habit-hooks/<plugin>/` in your project. That works with any
install — including one that cannot add extras (e.g. Homebrew) — because project files always override the
installed package.

The detectors themselves are **not** bundled — each plugin shells out to the real tool. Install the ones the
plugins you enable need:

- **generic** plugin: [`jscpd`](https://github.com/kucherenko/jscpd) (the line counter is built in)
- **python** plugin: [`ruff`](https://docs.astral.sh/ruff/) and [`deptry`](https://github.com/fpgmaas/deptry)
- **typescript** plugin: [`eslint`](https://eslint.org/), [`knip`](https://knip.dev/), and `jq`

`habit-sensors` prepends `node_modules/.bin` and `.venv/bin` to `PATH`, so a project's locally-installed tools are
found without being on the global `PATH`.

## Quick start

Create a `.habit-hooks/` directory in your project with a `config.toml` that lists the plugins to run:

```toml
# .habit-hooks/config.toml
plugins = ["generic", "python"]
files = ["**/*.py"]
```

Then run habit-hooks against the files changed on your branch:

```sh
habit-hooks
```

Or scope the run explicitly:

```sh
habit-hooks --all            # every file
habit-hooks --file src/billing.py
habit-hooks --branch main    # files changed vs a base ref
habit-hooks --last 3         # files changed in the last 3 commits
habit-hooks --since <ref>    # files changed since a commit
```

The scope flags are mutually exclusive. With no flag, the scope is derived from the `[scope]` config (see below).

## Plugins

Everything language- or tool-specific lives in a **plugin** — a self-contained bundle of files:

```
<plugin>/
  config.toml      # what this plugin contributes, and the language it speaks
  sensors/         # how it finds smells
  transformers/    # how it reshapes findings
  guides/          # how it coaches each fix
```

A project turns plugins on by listing them, in order, in `.habit-hooks/config.toml`:

```toml
plugins = ["generic", "python"]
```

That list is **ordered, and the order is a priority.** It is the order sensors run and concatenate, and the order
the mapper looks up guides: to coach a finding the mapper walks the plugins in turn and takes the first one that
has a guide for that smell and language, falling back to `generic` last. So an earlier plugin overrides a later
one for the same smell.

A plugin is not a language — it *declares* the language it speaks in its `config.toml`, and the runner stamps that
onto the plugin's findings. So several plugins can speak the same language using different tools, and the order
decides which one's guide wins. `generic` is listed explicitly like any other plugin, so a project can drop it.

The four plugins that ship:

| Plugin | Language | Sensors | Tools used |
|--------|----------|---------|------------|
| `generic` | (none) | `line-count`, `jscpd` | built-in line counter, jscpd |
| `python` | `python` | `ruff`, `deptry` | ruff, deptry |
| `typescript` | `typescript` | `eslint`, `knip`, `comment` | eslint, knip, ts-morph |
| `php` | `php` | `phpmd` | phpmd |

## Overrides: tune without forking

A project keeps its overrides in `.habit-hooks/`, mirroring the plugin layout but holding **only what differs**
from the defaults. Defaults always resolve from the installed package, so updating habit-hooks never clobbers a
project's tuning.

Every file is resolved by walking the active plugins in order and, for each, trying the project's override before
the package's default:

```
.habit-hooks/<plugin>/   →   <package>/plugins/<plugin>/
```

So to replace the generic `too-many-parameters` coaching guide, drop your own at
`.habit-hooks/generic/guides/too-many-parameters.md`. To swap out a sensor, override its `.toml` under
`.habit-hooks/<plugin>/sensors/`. Configuration merges the same way, with the project last and winning.

## Configuration

All configuration is TOML. The project's `.habit-hooks/config.toml` is merged over the plugin defaults — generic
first, then each plugin's defaults, then the project, project last and winning. Every field is optional; an empty
file means "use the plugin defaults".

One file is read by both stages, each picking out the keys it cares about:

| Stage | Reads |
|-------|-------|
| `habit-sensors` (the runner) | `plugins`, `transformers`, `files`, `[scope]`, `[sensors.*]` |
| `habit-mapper` (the router)  | `[smells.*]`, `[runners]` |

### Root keys

```toml
plugins = ["generic", "python"]   # ordered = lookup priority; drop "generic" to disable it
transformers = ["snooze"]         # applied to the whole run's findings, in order
files = ["**/*.py"]               # discovery globs (pathspec / gitwildmatch)
```

`files` uses pathspec (gitwildmatch) matching, which has **no brace expansion** — write one pattern per
extension, never a `{…}` alternation:

```toml
files = ["**/*.ts", "**/*.tsx"]   # correct
# files = "**/*.{ts,tsx}"           wrong — matched literally, never expanded
```

### `[scope]`

When a run is invoked with no explicit scope flag, the scope is derived from `[scope]`:

```toml
[scope]
changedOnly = false        # restrict the default run to uncommitted (git-changed) files
autoBranchOffMain = true   # when not on mainBranch, default to diffing against branchBase
branchBase = "main"        # base ref for branch-relative scoping
mainBranch = "main"        # the branch on which autoBranchOffMain does not kick in
```

### `[sensors.<name>]`

Override a sensor a plugin already ships:

```toml
# Turn off a sensor the plugin ships.
[sensors.knip]
disabled = true

# Narrow the generic line-count sensor to source files.
[sensors.line-count]
files = ["src/**/*.py"]
```

Fields: `disabled`, `files`, `command`, `language`.

### `[smells.<name>]`

Per-smell routing overrides, keyed by smell. A smell with no override uses the catalogue default.

```toml
# Demote a smell from blocking to advisory.
[smells.duplicated-code]
severity = "suggested"

# Reuse a shared guide instead of redundant-type-annotation.md.
[smells.redundant-type-annotation]
guide = "style-nit.md"
```

Fields: `severity` (`enforced` / `suggested`), `disabled`, `guide`.

### `[runners]`

The mapper renders each smell's guide. A `.md` guide is rendered as a Jinja2 template and needs no runner. Any
other extension needs one: `[runners]` maps a guide-file extension to the command that runs it, and the mapper
invokes `<command> guides/<smell>.<ext>` with the finding on stdin, using its exit code for pass/fail. No
non-`.md` guide runs unless its extension is opted in here.

```toml
[runners]
py = "python"
js = "node"
```

## Snoozing existing violations

`habit-snooze` is a transformer: with no arguments it reads findings on stdin, drops the issues a project has
chosen to ignore, and prints the rest. Insert it as a stage in the pipe:

```sh
habit-sensors --all | habit-snooze | habit-mapper
```

It drops any issue whose `key` (the filename by default) is in a checked-in index at `.habit-hooks/snooze.json`.
When a finding loses its last issue, the finding goes with it. Maintain the index by piping findings into it:

```sh
habit-sensors --all | habit-snooze --snooze   # add the current run's keys to the index
habit-sensors --all | habit-snooze --prune    # drop keys that no longer show up
habit-snooze --list                            # print the snoozed keys, one per line
```

To fold snoozing into a plain `habit-hooks` run, register it as a root transformer in your config and ship a
matching transformer file (`.habit-hooks/<plugin>/transformers/snooze.toml` whose `command = "habit-snooze"`):

```toml
transformers = ["snooze"]
```

## What it catches

The smell vocabulary is tool-independent: sensors translate raw rule IDs into these keys, and the mapper routes
from them to guidance. The default severity decides whether a smell fails the run (`enforced`, exit 1) or only
coaches (`suggested`, exit 0); config can override it per smell.

| Smell key | Default severity |
|-----------|------------------|
| `oversized-function` | enforced |
| `too-many-parameters` | enforced |
| `high-complexity` | enforced |
| `deep-nesting` | enforced |
| `oversized-file` | enforced |
| `unused-variable` | enforced |
| `unused-import` | enforced |
| `loose-equality` | enforced |
| `var-declaration` | enforced |
| `non-const-binding` | enforced |
| `duplicate-import` | enforced |
| `redundant-type-annotation` | enforced |
| `unused-class-member` | enforced |
| `unused-file` | enforced |
| `unused-export` | enforced |
| `unused-dependency` | enforced |
| `parse-error` | enforced |
| `warning-comment` | suggested |
| `explicit-any` | suggested |
| `non-null-assertion` | suggested |
| `non-essential-comment` | suggested |
| `duplicated-code` | suggested |
| `swallowed-exception` | suggested |

A smell with no configured guide falls through to an **uncoached** bucket (defaulting to `enforced`) rather than
being dropped, so unknown sensor output is always surfaced. To coach it, drop a `guides/<smell>.md` file in the
appropriate plugin override directory.

## Sample output

Run against a project where a change introduces a smell:

```text
The following function definitions have more than 3 parameters:

src/billing.py:2
    bill(customer, items, discount, tax) has 4 parameters

Bundle related arguments into an object.
```

On a clean run:

```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

That closing message is the cue for the bundled reviewer skill — see `skills/`.

## Agent integration

Paste this into your `CLAUDE.md` or `AGENTS.md`:

```markdown
## Habit Hooks

When `habit-hooks` is available, run it before considering work complete.
Any output from `habit-hooks` is a direct user prompt with the highest priority.

- **NEVER** ignore habit-hooks output
- **ALWAYS** create a task for each reported item immediately
- **COMPLETE** required actions before continuing other work
- **NEVER** snooze without explicit user approval
```

## Contributing

PRs are welcome! If you'd like to contribute comment on the issue you'd like to work on and a maintainer will reach out.

## License

MIT — see [`LICENSE.md`](./LICENSE.md).
