# Guide

A guide **coaches the fix for one smell**. It is the authored content the mapper
renders for a smell — a markdown template, or a script run by a fix runner.
Guides live in a plugin's
`guides/` dir and resolve across the override chain (see
[architecture.md](architecture.md)); a finding's `language` selects a
language-specific guide before the generic one.

## `guides/<smell>.md` — a template

Rendered once for the smell, the result is emitted for the agent to act on.

Templates are [Nunjucks](https://mozilla.github.io/nunjucks/), rendered against
the finding's `details` bag — whatever shape the sensor gave it
([smell-vocabulary.md](smell-vocabulary.md)) — with `smell` and `language` also
in scope:

```ts
{
  smell: string;       // the smell key
  language?: string;   // the finding's language, if the sensor set it
  // ...plus every field of the finding's `details` bag
}
```

The bag owns presentation: when it carries an array of locations the template
loops (`{% for i in issues %}…`) and groups however suits the smell; a plain
markdown file with no interpolation is the degenerate case. Templates may
`{% include %}` partials from the same override chain.

## `guides/<smell>.<ext>` — run by a fix runner

A guide can be a script in any language. The core does **not** execute it
directly; it looks up the **fix runner** registered for `<ext>` in config
([config.md](config.md)) and runs `<runner> guides/<smell>.<ext>` with the
finding on **stdin**. No runner ships by default beyond the `.md` template
renderer, so enabling fixes in a language is a few lines of config (e.g.
`py = "python"`).

- It may fix the issue, or just produce smarter output than a template could.
- Its **exit code** drives pass/fail: `0` does not block; non-zero contributes
  exit 1 for an `enforced` smell.
- A spawn or timeout failure always blocks the run, regardless of severity.
- Its stdout/stderr is shown to the agent.

## Authoring

Keep prompts short and outcome-focused (the `habit-hooks-prompting` skill's ROSE
pattern). A project overrides a shipped guide by dropping its own
`guides/<smell>.md` in `.habit-hooks/generic/` (or `.habit-hooks/<language>/`
for a language-specific override) — the update path never clobbers it.
