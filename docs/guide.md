# Guide

The guide **coaches the fix and gates the commit**. It consumes the
`GuideAction`s the mapper produced, renders agent-facing output, and computes
the process exit code. It never mutates code.

## Actions

### `prompt` (default)

Emit the smell's guidance markdown. This is the normal Habit Hooks behaviour:
the agent reads the prompt and performs the edit itself.

- Output: the rule title + description + the guidance markdown, followed by
  the offending `file:line`s (capped per group), grouped by smell.
- Exit contribution: an `enforced` smell with any issue contributes
  `exitCode = 1`; a `suggested` smell contributes `0`.

### `command` (override — lowest priority feature)

Run an arbitrary shell command instead of emitting a prompt. This is the
escape hatch for Llewellyn's "trigger a method/fixer" preference (e.g. run
`eslint --fix`, or a custom script) rather than coaching.

```jsonc
{ "smells": { "duplicated-code": { "command": "scripts/dedupe.sh ${file}" } } }
```

- `${file}` / `${line}` / `${smell}` expand per issue. The command runs once
  per issue (subject to change if we add a batched mode).
- The command's **exit code** drives the gate, mirroring Llewellyn's
  contract:
  - `0` — the issue is considered fixed/handled; it does not block.
  - non-zero — the issue is unresolved; contributes `exitCode = 1` for an
    `enforced` smell.
- The command's stdout/stderr is shown to the agent.

Because we don't know what executable a user wants, this is a bash call, not
an in-process function. We deliberately do **not** load arbitrary in-process
fixer functions — the command boundary covers the use case without the
complexity and security cost. *(Agent decision — revisit if in-process state
turns out to be needed.)*

This feature is the **lowest priority** in the roadmap; the default
prompt-based flow ships and stabilises first.

## Exit code summary

| Situation | Exit code |
|---|---|
| No issues | 0 |
| Only `suggested` smells | 0 |
| Any `enforced` smell with an unresolved issue | 1 |
| `command` action exits 0 for all its issues | does not block on its own |

A clean run prints the pass banner and a reminder that structural checks are
not a substitute for a correctness/design review.
