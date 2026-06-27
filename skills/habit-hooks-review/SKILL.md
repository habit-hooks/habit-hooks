---
name: habit-hooks-review
description: "Spawn a reviewer sub-agent to assess a change set against habit-hooks's coding principles. Use AFTER habit-hooks reports clean — habit-hooks catches structural smells; this catches what it cannot (correctness, tests, design, missed edge cases)."
---

# Habit Hooks Review

You are reading this because `habit-hooks` reported clean and you (the implementing agent) need a second pair of eyes on the change set before declaring the work done.

A green habit-hooks run is necessary, not sufficient. habit-hooks catches structural smells — oversized functions, high complexity, `any`, dead bindings, stale `TODO`s, comments standing in for unclear code. It cannot see:

- Correctness bugs (logic errors, off-by-one, wrong branch taken).
- Design issues (wrong abstraction, leaky boundaries, missing seam).
- Test coverage gaps (a happy path test masquerading as full coverage, untested error paths).
- Missed edge cases (empty input, concurrent calls, mid-iteration mutation).
- Naming clarity (a name that reads fine in isolation but is wrong for the role it plays).
- Missing abstractions that do not trip a threshold (two functions that should share a type, three call sites that should share a helper).

This skill spawns a reviewer sub-agent to look for exactly those things.

## How to invoke

Use the `Task` tool to spawn a `general-purpose` sub-agent with the brief below. Do **not** review the change yourself first — the value of this skill is the fresh read. Include the diff scope (commit range, branch, or staged files) in the brief so the reviewer knows what to look at.

## The brief

Paste this verbatim into the Task tool's `prompt`, filling in the change-set scope at the top:

---

You are reviewing a change set against the principles below. The implementing agent has already run `habit-hooks` and it reports clean — so structural smells (function size, parameter count, complexity, file length, `any`, unused vars, etc.) are already covered. **Do not re-flag anything habit-hooks catches.** Focus on what habit-hooks cannot see.

**Change set under review:** `<describe scope: commit range, branch diff, or staged files>`

**Ground rules:**

- PASS-when-clean is the right answer. Do not manufacture issues to look thorough.
- If the change is small and well-shaped, say so. A two-line PASS is a valid outcome.
- Cite `file:line` for every finding. No vague "consider revisiting the design" — point at something.
- Assume the change was written TDD-first. If tests are missing or asymmetric (only happy paths, only the new code), say so.

**Principles to review against:**

- **KISS** — is there a simpler approach that does the same job?
- **Single responsibility** — does each new function/class have one reason to change?
- **Naming clarity** — does every name reveal intent? Can a future reader understand it in five seconds?
- **Readability** — is the change comfortable to navigate, or does it ask the reader to hold too many ideas?
- **No shortcuts** — flag `eslint-disable`, `@ts-ignore`, `as any`, swallowed catches, magic numbers without context. Even if the linter is happy, those are debts.
- **Correctness** — read the logic, not just the shape. Look for off-by-one, wrong-branch, swallowed errors, race conditions, mid-iteration mutation.
- **Edge cases** — empty input, single-element input, max/min, error paths.
- **Test coverage** — is each new behaviour exercised? Are failure modes tested, not just happy paths?

**Categorise findings:**

- **Blocking** — must be fixed before merge. Correctness bugs, broken tests, gate failures, missing test for new behaviour.
- **Worth flagging** — design or clarity issues the author should weigh. Not necessarily blocking, but worth a conversation.
- **Nits** — small polish items. Hard cap: **two**. If you have more than two nits, drop the weakest ones.

**Confirm the gate:**

Run (or read the most recent output of) all four scripts: `typecheck`, `lint`, `test`, `build`. Detect the package manager from the lockfile in the project root (`pnpm-lock.yaml` → `pnpm`, `yarn.lock` → `yarn`, `bun.lock` or `bun.lockb` → `bun`, otherwise `npm`) and invoke accordingly — pnpm/yarn/bun take the script name directly (`pnpm typecheck`), npm needs `run` (`npm run typecheck`).

All four must exit 0. Report each exit code in the output.

**Output format (return this verbatim):**

```
## Verdict
<PASS | CHANGES NEEDED>

## Findings

### Blocking
- <file:line — one-line summary. One short paragraph of detail.>
- (or: "None.")

### Worth flagging
- <file:line — one-line summary. One short paragraph of detail.>
- (or: "None.")

### Nits (max 2)
- <file:line — one-line summary.>
- (or: "None.")

## Gate output
- typecheck: exit <code>
- lint: exit <code>
- test: exit <code>
- build: exit <code>

## Specific calls
<Anything that does not fit the categories above — design questions for the author, a follow-up worth scheduling, a pattern worth a CLAUDE.md note. Keep it short or omit the section entirely.>
```

---

## After the reviewer returns

- If **PASS**: relay the verdict and finish the task.
- If **CHANGES NEEDED**: do not silently fix everything. Surface the findings to the user, agree which to act on, and only then implement. Blocking items must be resolved; worth-flagging items are a conversation, not an assignment.

## Why this is a separate skill from `code-style-review`

`code-style-review` is invoked by a human, on a file or a region, to start a discussion before refactoring. It lists problems for the human to triage and prioritise.

`habit-hooks-review` is invoked by an agent, after a clean automated gate, to get a second-pass quality read on a finished change set. The shape of the output is different — verdict-driven, scoped to the diff, framed for an agent that is about to declare done.

The two skills are complementary, not interchangeable. Do not use `code-style-review` as a stand-in here: it will not check the gate, will not categorise by blocking severity, and will not return a verdict.
