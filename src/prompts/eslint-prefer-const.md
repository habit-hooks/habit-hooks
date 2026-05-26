A `let` that is never reassigned signals to the reader that reassignment is possible — that is a lie. Switch to `const` so the binding's immutability is visible at the declaration site.

If you almost reassigned but found a cleaner way (early return, ternary, separate binding), keep it as `const` rather than reverting to `let`.
