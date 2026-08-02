`var` doesn't scope to the block it sits in — it hoists to the whole function and silently allows redeclaration. So a `var` inside an `if`, a loop, or a `try` leaks to every line after it, a loop-captured `var` shares one binding across all iterations (the classic "every callback sees the last value" bug), and a second `var` of the same name is a no-op rather than the error it should be. The declaration lies about where the variable lives.

Replace it with `const`, and use `let` only when the binding is genuinely reassigned. Both scope to the block, so the variable exists exactly where it's written and nowhere else, and a stray redeclaration becomes a compile error instead of a silent overwrite. Reaching for `const` first also surfaces the next smell for free: if `const` works, the binding was never reassigned, and the reader now knows that at a glance.

Done right, every declaration's scope matches its indentation, and the choice of `const` versus `let` tells the reader whether the value ever changes.

{% include "includes/line_level_issues.md" %}
