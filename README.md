# Habit Hooks

[![PyPI](https://img.shields.io/pypi/v/habit-hooks)](https://pypi.org/project/habit-hooks/) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/habit-hooks/) [![CI](https://github.com/habit-hooks/habit-hooks/actions/workflows/ci.yml/badge.svg)](https://github.com/habit-hooks/habit-hooks/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/habit-hooks/habit-hooks/blob/main/LICENSE.md)

**Turn best-practice coding advice into AI habits.**

Stop reciting software engineering literature to your AI agent. Habit Hooks runs your linters, then replaces
each raw rule violation with a short coaching guide the agent can act on — so it writes code like this:

![TypeScript written by an agent running Habit Hooks: small functions, named constants, no duplication](https://raw.githubusercontent.com/habit-hooks/habit-hooks/main/write_code_like_this.png)

> 👀 Looking for co-maintainers — see [Contributing](#contributing).

## Why

- AI coding agents ignore long rule documents. A book's worth of coding advice in the context window makes
  them worse, not better.
- Humans don't need it in their head. Repetition turns advice into habit, triggered by an easy-to-spot cue.
  Agents can't form habits.
- A bare linter score is a target, and Goodhart's law applies: agents are very good at gaming a target when
  the target is all they are given.
- Habit Hooks supplies the missing loop from outside. The linter finding is the cue; the coaching guide is
  the action.

The effect: better code, better agent performance on the next task, and fewer tokens — good code needs less
context to work in.

## Install

```sh
uv tool install habit-hooks     # pip, pipx and brew work too
cd your-project
habit-hooks init
```

`habit-hooks init` detects your project's language, writes `.habit-hooks/config.toml` enabling the plugins it
needs, and lists everything still missing beside the command that installs it — offering to run them for you.
Re-run it any time: on a configured project it changes nothing and only reports what is missing, so it also
answers "why is this run not reporting anything?".

<details>
<summary><b>Doing it by hand</b> — what <code>init</code> is doing on your behalf</summary>

Setup is four steps. A run that reports nothing is almost always a skipped one:

1. **Install habit-hooks** — you get the core and the generic, language-agnostic plugin.
2. **Install the plugin for your language** — python, typescript, php and java ship as separate packages.
3. **Enable the plugins** by naming them in `.habit-hooks/config.toml`. Installing one does not switch it on.
4. **Install the detectors** the plugins you enabled use — `jscpd`, `ruff`, `eslint` and friends.

Steps 3 and 4 are per project.

### 1. Install habit-hooks

A Python package, requires Python 3.11+:

```sh
uv tool install habit-hooks
# or
uvx habit-hooks
# or
pip install habit-hooks
# or
brew install habit-hooks/tap/habit-hooks
```

You get **core plus the generic plugin**, and four commands on your `PATH`: `habit-hooks`, `habit-sensors`,
`habit-mapper`, `habit-snooze`. Homebrew is the exception — it installs all five plugins, so skip to step 3.

> ⚠️ **On its own this checks nothing about your language.** The generic plugin measures file length and
> duplication. Python, TypeScript, PHP and Java each need their own plugin — installed (step 2) *and*
> enabled (step 3).

### 2. Install the plugin for your language

The four language plugins are **opt-in** via extras:

```sh
uv tool install "habit-hooks[typescript]"          # one language
uv tool install "habit-hooks[python,typescript]"   # several — name them in one command
uv tool install "habit-hooks[all]"                 # all four
```

> ⚠️ Each `uv tool install` **rebuilds** the environment rather than adding to it, so a second one naming a
> different extra silently replaces the first: run `[python]` then `[typescript]` and you are left with
> typescript alone, and your Python project quietly stops being checked. Name every language in one command.
> (`pip install "habit-hooks[python]"` has no such trap — it adds.)

To pick plugins per project without a global install, run from the extra with `uvx` (uv caches it):

```sh
uvx --from "habit-hooks[typescript]" habit-hooks
```

Alternatively, vendor a plugin's files under `.habit-hooks/<plugin>/` in your project. That works with any
install, because project files always override the installed package — including a plugin habit-hooks has no
package for.

### 3. Enable the plugins in your project

**Installing a plugin does not switch it on.** However it got onto the machine, a plugin runs only once your
`.habit-hooks/config.toml` names it:

```toml
# .habit-hooks/config.toml
plugins = ["typescript", "generic"]
```

The list is ordered, and the order is a priority — see [Plugins](#plugins).

### 4. Install the detectors

Detectors are **not** bundled: a plugin spawns the real tool, or reads it as a library.

| Plugin | Detectors | Install |
| ------ | --------- | ------- |
| **generic** | [`jscpd`](https://github.com/kucherenko/jscpd) — the line counter is built in | `npm install --save-dev jscpd` |
| **python** | [`ruff`](https://docs.astral.sh/ruff/), [`deptry`](https://github.com/fpgmaas/deptry), `jq` | `pip install ruff deptry` (`jq` from your system package manager) |
| **typescript** | `node`, [`eslint`](https://eslint.org/), [`knip`](https://knip.dev/), [`ts-morph`](https://ts-morph.com/), `jq` | `npm install --save-dev eslint knip ts-morph` (`node` and `jq` from your system package manager) |
| **php** | `php` — [phpmd](https://phpmd.org/) ships bundled as a phar | nothing beyond a PHP runtime |
| **java** | [`pmd`](https://pmd.github.io/) | `brew install pmd` |

`ts-morph` is read as a library rather than spawned, so it belongs in your `devDependencies` — being on `PATH`
does nothing for it.

> If your TypeScript project has **no eslint config of its own**, habit-hooks lints with the config it ships,
> which needs two more packages in your project:
> `npm install --save-dev @typescript-eslint/parser @typescript-eslint/eslint-plugin`. A project with its own
> `eslint.config.js` needs neither — yours always wins.

`habit-sensors` prepends `node_modules/.bin` and `.venv/bin` to `PATH`, so a project's local tools are found
without being installed globally.

</details>

## Usage

`habit-hooks init` writes the smallest config that runs — the plugins, and nothing else assumed:

```toml
# .habit-hooks/config.toml
plugins = ["python", "generic"]
```

Naming no `files` is the recommended start: the run then scans what the active plugins declare, **including
their exclusions** — the python plugin already keeps `.venv/` and `site-packages/` out. Adding your own
`files` replaces those wholesale, exclusions and all.

Then run it:

```sh
habit-hooks
```

That scans **every** file in scope — on an existing codebase, that is the whole backlog on your first run.

**Starting on an existing codebase? Snooze the backlog first.** One command records today's findings as
accepted, so from then on only *new* smells surface:

```sh
habit-sensors --all | habit-snooze --snooze
```

Commit the `.habit-hooks/snooze.json` it writes. Nothing is buried permanently — see
[Snoozing existing violations](#snoozing-existing-violations), which also covers the ratchet that brings a
file's issues back the moment you touch it.

Scope the run explicitly instead — the flags are mutually exclusive:

```sh
habit-hooks --all                   # every file
habit-hooks --file src/billing.py   # one file, ignoring snoozes
habit-hooks --branch main           # files changed vs a base ref
habit-hooks --last 3                # files changed in the last 3 commits
habit-hooks --since <ref>           # files changed since a commit
```

With no flag, the scope comes from `[scope]` in the config — which scans everything until you opt in. To make
a plain `habit-hooks` measure only your branch **when you are not on `mainBranch`**, set
`[scope] autoBranchOffMain = true`. On `mainBranch` itself it still scans everything.

A git-derived run measures what your branch changed since it left the base ref — from the **merge base**, so
files somebody else changed on the base afterwards are not yours to fix. Whatever picked the paths, files the
work tree no longer has are dropped, and the rest must match `files`. A base ref the checkout cannot resolve
fails the run rather than quietly scanning nothing.

### Exit codes

The exit code separates a finding from a broken tool, so a CI wrapper can act on the difference:

| Exit | Meaning |
| ---- | ------- |
| `0`  | clean — no enforced finding |
| `1`  | an enforced finding — this branch has a smell to fix |
| `2`  | the tool itself failed — a bad config key, an unresolvable base ref, a corrupt snooze index, or a plugin that is configured but not installed |

`habit-hooks --version` prints `habit-hooks vX.Y.Z` (likewise on the other three commands) — worth quoting in a
bug report, since the tool ships through four channels: PyPI, Homebrew, uvx and an npm shim.

## Sample output

When a change introduces a smell:

```text
── too-many-parameters (1 issue) ──

High parameter count is a sign of coupling.
Parameters that travel together across several calls are a missing abstraction.

**Find the missing abstraction:**
1. Look at the call sites and nearby functions — is there an existing class a group of these
   parameters belongs to? …

**AVOID**: A `{ ...everything }` bag that merely renames the list hides the coupling instead of
removing it. …

src/billing.py:1
```

(Guides are longer than this — the middle is trimmed here.)

On a clean run:

```text
✅ Habit Hooks: automated checks passed.

Habit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.
```

That closing message is the cue for the reviewer skill in the repo — see [`skills/`](https://github.com/habit-hooks/habit-hooks/tree/main/skills).

## How it works

Two command-line tools joined by a Unix pipe, with a JSON array of **findings** flowing between them:

```
habit-sensors <scope flags> | habit-mapper
```

- **`habit-sensors`** finds the smells — runs the configured detectors over the files in scope and emits a
  findings array on stdout.
- **`habit-mapper`** acts on them — groups findings by smell, renders each smell's coaching guide, and sets
  the exit code from each smell's severity. An empty pipe means a stage died before writing, so it coaches the
  incomplete run and exits 2 rather than reporting a pass.

`habit-hooks` is just the composition of the two, so the same arguments scope the run and the same findings
drive the coaching. Because the stages talk only through findings on a pipe, each can be run, tested or
replaced on its own.

Each sensor translates a tool's raw rule IDs into a tool-independent **smell key** (`max-params`, `PLR0913`, …
all become `too-many-parameters`), and everything downstream routes on that key alone. The mapper picks a
guide by smell, never by which tool reported it.

More: [`docs/architecture.md`](https://github.com/habit-hooks/habit-hooks/blob/main/docs/architecture.md).

## What it catches

`enforced` fails the run (exit 1); `suggested` coaches and exits 0. Config can override either per smell.

**Enforced** — `oversized-function` · `too-many-parameters` · `high-complexity` · `deep-nesting` ·
`oversized-file` · `unused-variable` · `unused-import` · `loose-equality` · `var-declaration` ·
`non-const-binding` · `duplicate-import` · `redundant-type-annotation` · `unused-class-member` ·
`unused-file` · `unused-export` · `unused-dependency` · `test-only-dead-code` · `parse-error`

**Suggested** — `warning-comment` · `explicit-any` · `non-null-assertion` · `non-essential-comment` ·
`duplicated-code` · `swallowed-exception`

A smell with no catalogue entry is never dropped — it falls through to an **uncoached** bucket, so unknown
sensor output is always surfaced. The root `uncoached` key decides what happens to it:

- `suggest` (default) — coach, but do not fail the run. The catalogue is the record of what is worth failing
  a build over, and this name is not in it.
- `enforce` — fail the run.
- `ignore` — drop it.

`[smells.<name>] severity` overrides all three for one smell. To coach it properly, drop a
`guides/<smell>.md` file in the appropriate plugin override directory.

`incomplete-run` is reserved: when a sensor or transformer breaks, or a stage dies before writing anything,
the run reports it under that key and exits non-zero rather than printing a clean result it cannot stand
behind.

Full list with descriptions: [`docs/smell-vocabulary.md`](https://github.com/habit-hooks/habit-hooks/blob/main/docs/smell-vocabulary.md).

## Plugins

Everything language- or tool-specific lives in a **plugin** — a self-contained bundle:

```
<plugin>/
  config.toml      # what this plugin contributes, and the language it speaks
  sensors/         # how it finds smells
  transformers/    # how it reshapes findings
  guides/          # how it coaches each fix
```

The five that ship:

| Plugin | Language | Sensors | Tools used |
|--------|----------|---------|------------|
| `generic` | (none) | `line-count`, `jscpd` | built-in line counter, jscpd |
| `python` | `python` | `ruff`, `deptry` | ruff, deptry |
| `typescript` | `typescript` | `eslint`, `knip`, `comment` | eslint, knip, ts-morph |
| `php` | `php` | `phpmd` | phpmd |
| `java` | `java` | `pmd` | pmd |

A project turns plugins on by listing them in `.habit-hooks/config.toml`. **That list is ordered, and the
order is a priority:**

- It is the order sensors run and concatenate.
- It is the order the mapper looks up guides — first plugin whose declared language matches the finding, then
  the languageless `generic`. A language plugin's guide wins over `generic`'s wherever `generic` sits in the
  list, so the order only decides a tie between two plugins declaring the same language.

A plugin is not a language: it *declares* the language it speaks in its `config.toml`, and the runner stamps
that onto its findings. So several plugins can speak the same language using different tools, and the order
decides whose guide wins. `generic` is listed explicitly like any other plugin, so a project can drop it —
but it holds 16 of the shipped guides against `typescript`'s 8 and `python`'s 2, so dropping it leaves most
smells uncoached.

Writing your own: [`docs/authoring-plugins.spec.md`](https://github.com/habit-hooks/habit-hooks/blob/main/docs/authoring-plugins.spec.md).

## Tune it without forking

A project keeps its overrides in `.habit-hooks/`, mirroring the plugin layout and holding **only what
differs**. Defaults always resolve from the installed plugin package, so upgrading habit-hooks never clobbers
your tuning. Every file is resolved by walking the active plugins in order and trying the project's override
before the package's default:

```
.habit-hooks/<plugin>/<file>   →   installed habit_hooks_<plugin> package data/<file>
```

To replace the generic `too-many-parameters` guide, drop your own at
`.habit-hooks/generic/guides/too-many-parameters.md`. To swap a sensor, override its `.toml` under
`.habit-hooks/<plugin>/sensors/`.

## Configuration

All configuration is TOML, in `.habit-hooks/config.toml`, merged over the plugin defaults — project last and
winning. Every field is optional. The most common keys:

```toml
plugins = ["python", "generic"]   # ordered; generic is the languageless fallback
files = ["**/*.py"]               # what this project counts as source, in every scope mode
uncoached = "suggest"             # what to do with a smell the catalogue has no entry for

[scope]                           # used when a run is invoked with no explicit scope flag
autoBranchOffMain = true          # OPT-IN (default false): off mainBranch, diff against branchBase
branchBase = "main"               # default; base ref for branch-relative scoping, must exist in the checkout
mainBranch = "main"               # default; the branch on which autoBranchOffMain does not kick in
changedOnly = false               # default; restrict the default run to uncommitted (git-changed) files

[sensors.knip]                    # turn off a sensor a plugin ships
disabled = true

[smells.duplicated-code]          # demote a smell from blocking to advisory
severity = "suggested"
```

Discovery is **opt-in**: leave `files` out and the run scans what its plugins declare. A project that names no
`files` and whose plugins declare none — a generic-only project — scans **nothing at all**, rather than
sweeping `node_modules`, `.venv` and `.git`. That project must name what it wants scanned.

> ⚠️ `files` uses pathspec (gitignore) matching, which has **no brace expansion**. Write one pattern per
> extension: `["**/*.ts", "**/*.tsx"]`, never `"**/*.{ts,tsx}"` — the alternation is matched literally.

Full field reference, including `transformers`, `[runners]` and every `[sensors.*]` / `[smells.*]` key:
[`docs/config.md`](https://github.com/habit-hooks/habit-hooks/blob/main/docs/config.md).

## Snoozing existing violations

Adopting Habit Hooks on an existing codebase would otherwise mean fixing everything at once. `habit-snooze` is
a transformer: it drops the issues a project has chosen to ignore and prints the rest.

```sh
habit-sensors --all | habit-snooze --snooze              # add the current run's keys to the index
habit-sensors --all --no-snooze | habit-snooze --prune   # drop keys that no longer show up
habit-snooze --list                                      # print the snoozed keys
```

`--prune` needs `--no-snooze`: a plain `habit-sensors` has already dropped every snoozed finding, so pruning
against it would see none of them and empty the whole index.

The index is a checked-in `.habit-hooks/snooze.json`. Snoozing is already folded into a plain `habit-hooks`
run — `transformers` defaults to `["snooze"]` — so a checked-in index takes effect with no wiring.

The index is portable by construction: every path a sensor reports is re-expressed relative to the project
before a key is formed, so an index recorded on your machine matches on a teammate's checkout and in CI, even
though `ruff` and `eslint` report absolute paths.

**Make it a ratchet.** A plain snooze holds until someone edits the index, so a snoozed file stays exempt even
after it doubles in size. Swap in the second transformer:

```toml
transformers = ["snooze-until-changed"]
```

An exemption then holds only while its file is unchanged since your branch left `[scope] branchBase`. Touch
the file and its issues come back — which is exactly when you are in a position to clear them.

Details, including how `--file` bypasses the index:
[`docs/habit-snooze.spec.md`](https://github.com/habit-hooks/habit-hooks/blob/main/docs/habit-snooze.spec.md).

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

PRs are welcome **after** discussion. Comment on the issue you'd like to work on and a maintainer will reach
out.

**We are looking for co-maintainers.** It means joining a weekly planning meeting, shaping where this tool
goes, and working with likeminded software crafters who care about quality. If that appeals, reach out to
[Ivett Ördög](https://ivettordog.com) directly.

## License

MIT — see [`LICENSE.md`](https://github.com/habit-hooks/habit-hooks/blob/main/LICENSE.md).
