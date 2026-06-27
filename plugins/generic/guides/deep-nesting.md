Deeply nested blocks — `if` inside `for` inside `try` inside `if` — force the reader to hold every enclosing condition in their head at once. The smell is not the indentation; it is that the function is doing too much branching in one place.

Read the nesting from the inside out and ask what the innermost block actually needs. Usually most of the enclosing conditions are *guards* — preconditions that should be checked and bailed on early, not wrapped around the real work.

Prefer, in order:

1. **Guard clauses / early returns.** Invert a condition and `return` (or `continue`/`throw`) early so the happy path stays at the top indentation level. Each guard you lift removes one level of nesting from everything below it.
2. **Extract a helper.** When an inner block is a coherent sub-step, pull it into a named function. The name documents the intent and the nesting moves into a flat, separately-readable unit.
3. **Replace the structure.** A deep `if/else` ladder is often a lookup table or a polymorphic dispatch in disguise; a nested loop is often a `filter`/`map`/`flatMap` pipeline.

Avoid the mechanical fix of merging conditions with `&&` just to drop a level — that trades vertical nesting for an unreadable horizontal condition. The goal is a function whose shape you can take in at a glance, not one that merely passes the depth threshold.

If the nesting is genuinely irreducible (a real algorithm with interacting conditions), extracting the inner loops into well-named helpers is still the move: keep each function shallow even when the algorithm as a whole is deep.
