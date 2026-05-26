The `!` operator tells TypeScript "trust me, this is not null" — and at runtime nobody is checking. When the assumption breaks you get a `Cannot read properties of undefined` with no clue why.

Prove the value is present: an `if`-guard with an early return, an `assert`, `??` with a sensible default, or restructure so the optional case is impossible at the call site.
