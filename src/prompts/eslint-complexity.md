High cyclomatic complexity means a function carries too many decisions — it is harder to understand, harder to test exhaustively, and a frequent home for bugs. The smell is mixed concerns, not the number itself.

High complexity often indicates multiple responsibilities. Look for: (1) decision trees that could be strategy patterns or a lookup table, (2) multiple concerns that belong in separate methods, (3) state machines that could be explicit classes with named states.

Focus on extracting *meaningful* abstractions, not just shaving complexity metrics. Splitting one `if/else` chain into three nested helpers usually moves the complexity around without making the code clearer.

If the code has many misplaced responsibilities you may need to first *inline* methods to see the whole picture and find a better way of redistributing functionality. Think of this when reducing complexity seems particularly hard — taking a step backwards may open up new, better possibilities.
