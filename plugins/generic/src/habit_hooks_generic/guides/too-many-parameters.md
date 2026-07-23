Long parameter lists violate single responsibility — the function is doing too much, or it is operating on data that belongs together as an object the function should live near.

Before grouping parameters into a bag-of-fields object, ask: (1) Should this method actually belong *on* the parameter object as a class method? A free function taking five fields from the same record is often a class method waiting to happen. (2) For static methods with many parameters — this is very often a class waiting to happen. (3) Group cohesive data into meaningful objects and pass those around, even if some methods do not need every field.

Favour a declarative style over many locals — once data clusters into objects, control flow usually simplifies too.

A literal `{ ...everything }` object that just renames the parameter list does not address the smell; it hides it.

A concrete technique: write the calling sites you wish existed (one line each). Make them real — the parameter shape usually falls out of the call sites you want.

{% include "includes/line_level_issues.md" %}
