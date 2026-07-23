High cyclomatic complexity means one function makes too many decisions at once. The count is the symptom; tangled responsibilities are the cause.

**Untangle the decisions:**
1. Lift guards out first — turn precondition checks into early returns so the happy path stays flat. Much of the count is preconditions wrapped around the real work.
2. Change the shape of what remains: an `if`/`else` chain switching on one value is often a lookup table or polymorphism in disguise; a nested loop is often a filter/map pipeline.
3. If the branches are genuinely separate jobs, extract one function per branch, each named for the responsibility it handles.

Useful tip: describe each branch in one sentence. Two branches with the same sentence belong together; a branch you cannot name cleanly wants its own function.

**AVOID**: merging conditions with and/or, or rewriting branches as ternaries, just to lower the score — the decisions remain, only the counter moves. You are done when a first-time reader can hold the whole function in their head.

{% include "includes/line_level_issues.md" %}
