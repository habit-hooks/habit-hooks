High cyclomatic complexity means one function is making too many decisions at once. The smell is not the number, it is that the function has quietly taken on more than one job. The count is the symptom, tangled responsibilities are the cause.

Work through it in order:

1. **Name what each branch is for.** Give every branch a one-sentence description of the responsibility it handles. If two branches describe the same thing, they belong together. If a branch has no clean name, that path probably wants its own function.
2. **Lift the guards out first.** Turn early-exit conditions into guard clauses (`if not user: return None`) so the happy path stays flat and left-aligned. Most of the count is preconditions wrapped around the real work.
3. **Change the shape, do not just move it.** When every branch is the same kind of decision, reshape it: a long `if/elif` on a value is often a dict dispatch or polymorphism, a nested loop often a comprehension or a generator. When polymorphism is not the right fit and the branches are genuinely separate jobs, extract one named method per branch, each named for the responsibility it handles. The goal is fewer decisions in one place, not the same tangle split into `_part1` / `_part2` behind worse names.

Reducing the number without reducing the tangle is not a fix. Do not merge conditions with `and`/`or` just to drop a branch, and do not rewrite `if` statements as ternaries to slip under the check. ruff's mccabe does not count ternary expressions, so that trick lowers the score while a human still has to hold every condition in their head.

The test is not whether the number dropped. It is whether someone reading the function for the first time can hold it in their head at once. If not, it is still doing too much.

{% include "includes/line_level_issues.md" %}
