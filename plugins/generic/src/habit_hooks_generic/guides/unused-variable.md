An unused local variable is dead weight: the reader has to prove to themselves it does not matter. It usually signals one of three things — a computation whose result is never consumed (delete the computation, not just the assignment), a leftover from a refactor that moved logic elsewhere, or a value you meant to use and forgot to wire in (the real bug).

Decide which it is before deleting. If the right-hand side has side effects you still need, keep the call but drop the binding. If it was meant to be returned or passed on, finish that thread rather than silencing the warning. Suppressing it with a throwaway name hides the question instead of answering it.

{% include "includes/line_level_issues.md" %}
