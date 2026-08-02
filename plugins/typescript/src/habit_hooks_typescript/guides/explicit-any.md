`any` doesn't add a type — it deletes one. Every value that flows through an `any` loses its guarantees, and the loss is contagious: the compiler stops checking property access, calls, and assignments along that path, so a rename or a shape change three files away fails silently at runtime instead of loudly at build. One `any` quietly disables the tool you're paying for.

Name the real type. If the shape is known, write it — an interface, a type alias, a union of the cases that actually occur. If it's genuinely a value whose shape you can't know yet (a parsed JSON blob, a third-party payload), reach for `unknown`, which forces a check at the boundary before the value is used, instead of `any`, which waves it through. When the awkwardness is that the type varies with an input, that's a signal for a generic parameter, not an escape hatch. If you're modelling an external API, describe it once in a typed declaration and import that.

Done right, the value carries a type the compiler can check end to end, and the class of "worked in dev, undefined in prod" bug this invites is gone.

{% include "includes/line_level_issues.md" %}
