A long parameter list is the symptom. The defect is a concept with no name — values that always travel together and were never made a thing.

{% include "includes/line_level_issues.md" %}
Grouping them into a bag named after the function that takes them — a `FooProps`, an options object, `{ ...everything }` — clears the report and entrenches the smell. Such an object is organised by method rather than by abstraction: the next function invents another bag, and the concept stays unnamed.

Name the entity instead, and use domain-driven design to find it: parameters that travel together are usually one of the domain's own nouns. Search the rest of the codebase for the same values appearing side by side — the combinations that recur are the real entity, and where one already carries a name, that name is the answer. Then ask whether this function belongs *on* it.

Refactor every site the new entity fits, not only the one that fired. An abstraction used in one place is hidden, not introduced, and a call passing three of its fields is the same concept sitting under the threshold.

Done right: the entity carries a domain name, its call sites read as statements about it, and nowhere in the codebase still passes its fields loose.
