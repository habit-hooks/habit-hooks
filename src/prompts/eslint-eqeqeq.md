`==` triggers silent type coercion (`0 == ''`, `null == undefined`, etc.) that hides real bugs. Use `===` and `!==`.

If you genuinely need `null`-or-`undefined` semantics, say so explicitly: `value == null` is sometimes argued for, but a `value === null || value === undefined` (or a dedicated nullish check) reads more honestly.
