An annotation the compiler would infer identically (`const n: number = 1`, `const s: string = "x"`) is not extra safety — it is a second copy of a fact, and two copies drift. Change the initializer and the annotation now lies until someone updates it too; the reader can't tell whether the type is asserting an intent or just restating the obvious, so it stops carrying meaning.

Delete the annotation and let inference do its job. The type is not lost — hover shows it, and the compiler still checks every use. Keep an explicit type only where it does work inference cannot: widening a literal to a union you intend to extend, pinning a function's parameter and return types as its contract, or annotating a `let` whose first assignment shouldn't narrow it. Those are deliberate; a restatement of the initializer's own type is not.

Done right, an explicit type on a value means "I am choosing this, not what you'd guess" — so every annotation that remains is a signal, not noise.

{% include "includes/line_level_issues.md" %}
