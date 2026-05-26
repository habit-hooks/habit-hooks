`any` opts out of the type checker — every property access, call, and assignment becomes unchecked. The bug it hides next will be silent.

Prefer a precise type. When the shape really is unknown (parsed JSON, external input), use `unknown` and narrow with a type guard at the boundary. Casting through `as Foo` only moves the problem.
