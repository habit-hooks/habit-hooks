`==` and `!=` run the type-coercion algorithm before comparing, and its rules are the kind nobody keeps straight: `0 == ""`, `null == undefined`, `[] == ![]` are all true, and `NaN` equals nothing at all. The result is a comparison that reads as "are these the same" but silently answers a different, coercion-warped question — the exact ground bugs hide in, because the code looks obviously correct.

Use `===` / `!==`, which compare value and type with no coercion, so the check means what it says. The one place `==` is genuinely useful is `x == null`, the idiomatic way to catch `null` and `undefined` together; if that's the intent, keep it deliberately rather than by accident. When you *do* need to compare across types, don't lean on coercion to hide it — convert explicitly (`Number(x) === y`, `String(x) === y`) so the conversion is visible and its failure modes are yours to see.

Done right, every equality in the file compares like with like, and no comparison depends on a coercion table to be correct.

{% include "includes/line_level_issues.md" %}
