High cyclomatic complexity means a function carries too many decisions — harder to understand, harder to test exhaustively, a frequent home for bugs. The smell is mixed concerns, not the number itself.

High complexity often indicates multiple responsibilities. Look for: (1) decision trees that could be strategy patterns or a lookup table, (2) multiple concerns that belong in separate methods, (3) state machines that could be explicit classes with named states.

Focus on extracting *meaningful* abstractions, not just shaving complexity metrics. Splitting one `if/else` chain into three nested helpers usually moves the complexity around without making the code clearer.

If responsibilities are tangled you may need to first *inline* methods to see the whole picture before redistributing. Think of this when reducing complexity seems particularly hard — stepping backwards often opens up better possibilities.

A concrete technique: name each branch by the responsibility it handles. If two branches resolve to the same one-sentence description, they belong together; if one branch has no clear name, that path probably belongs in a separate function or class.
