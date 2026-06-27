---
name: habit-hooks-prompting
description: "Write or revise a habit-hooks coaching prompt. Use when a linter / knip / jscpd rule fires and the agent's default fix is wrong or shallow, or when adding a project-local override prompt. Keeps prompts short and outcome-focused using the ROSE pattern."
---

# Habit Hooks Prompting

Coaching prompts exist to **change behaviour the agent gets wrong by default** — nothing else.

The goal of every prompt is to drive the agent to **fix the root cause the violation points at, not to appease the reporting tool.** A fix that clears the report while going against the spirit of the rule is a failure, even when the tool goes green.

## When to write one

- The rule's own message already produces the right fix → **write nothing.** Let it fall through to the uncoached prompt. Don't coach what already works.
- The agent's default reaction is shallow or wrong — mechanical extraction that misses the real design problem, silencing instead of fixing, a reflexive `eslint-disable` → write a prompt that redirects it.

This is reactive: add a prompt the moment you catch the default behaviour being wrong, not pre-emptively for every rule.

## Keep it short (KISS)

A good prompt is the **minimum text that reliably nudges the right behaviour**. If it reads like an essay, cut it — direction beats explanation. The agent already has the violation in front of it.

## Use ROSE

ROSE structures feedback so the agent understands *why*, not just *what*, and fixes the cause rather than the symptom:

- **R**isk — the consequence of leaving it as-is.
- **O**bservation — what was seen. **The linter already supplies this** (file, line, rule); don't repeat it.
- **S**olution — the specific move you want, including the non-obvious one the agent tends to miss.
- **E**xpected outcome — what "done right" looks like, so the agent can check itself.

So a habit-hooks prompt writes **R, S, E** and lets the tool supply **O**. See `eslint-fatal.md` and `eslint-typescript-eslint-no-non-null-assertion.md` for prompts in this shape.

## Where prompts live

- Bundled: `src/prompts/<slugified-rule-id>.md` (`:` and `/` → `-`, `@` dropped).
- Project-local override: a file of the same name in the directory set by `prompts:` in `habit-hooks.config`.
