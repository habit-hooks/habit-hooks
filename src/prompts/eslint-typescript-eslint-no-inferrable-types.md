`const count: number = 0` repeats what TypeScript already knows. Drop the annotation; the inferred type is identical and the declaration reads more cleanly.

Keep annotations where they document an interface contract (function signatures, exported constants where the literal type would be too narrow), not where they restate the obvious.
