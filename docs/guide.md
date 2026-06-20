# Guide

The guide **coaches the fix and signals pass/fail**. It consumes the
`GuideAction`s the mapper produced, renders agent-facing output, and computes
the process exit code. Whatever invokes Habit Hooks — an agent loop, a git
hook, CI — decides what a non-zero exit means.

## Actions

### `prompt` — a `.md` template

Render the smell's **template** against all of its issues and emit the
result; the agent reads it and performs the edit.

The template owns presentation — including how issues are grouped, so each
smell groups the way that suits it:

- `oversized-function` — by file
- `duplicated-code` — by the duplicated block
- `primitive-obsession` — by the data structure, across files

A plain markdown file with no interpolation is the degenerate case.

An `enforced` smell with any issue contributes exit 1; `suggested`
contributes 0.

#### Template context

Templates are [Nunjucks](https://mozilla.github.io/nunjucks/), rendered once
per smell with all of that smell's issues:

```ts
{
  smell: string;          // the smell key
  issues: Issue[];        // every issue for this smell (each with its details bag)
}
```

Grouping (`{% for %}`, the `groupby` filter), filtering, and counts are the
template's responsibility, using the fields the sensor put in each issue's
`details`.

### `command` — any other file

Run a script instead of rendering a template. The script is plain bash or
PowerShell named after the smell (mirroring `<smell>.md`), and receives the
smell's **issues** as a JSON array (`Issue[]`) on stdin. It runs once per
smell.

- The script may or may not fix the issues — sometimes it just produces
  smarter output than a template can.
- Its **exit code** drives pass/fail: `0` means handled (does not block);
  a non-zero exit contributes exit 1 for an `enforced` smell.
- A spawn or timeout failure (the script can't run) always blocks the run,
  regardless of severity.
- Its stdout/stderr is shown to the agent.

## Exit code summary

| Situation                                     | Exit code                 |
|-----------------------------------------------|---------------------------|
| No issues                                     | 0                         |
| Only `suggested` smells                       | 0                         |
| Any `enforced` smell with an unresolved issue | 1                         |
| `command` script exits 0                      | does not block on its own |
| `command` script fails to spawn / times out   | 1 (always blocks)         |

A clean run prints the pass banner and a reminder that structural checks are
not a substitute for a correctness/design review.
