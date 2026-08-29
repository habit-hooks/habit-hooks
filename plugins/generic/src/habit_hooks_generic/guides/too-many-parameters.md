High parameter count is a sign of coupling.
Parameters that travel together across several calls are a missing abstraction.

**Find the missing abstraction:**
1. Look at the call sites and nearby functions/methods — is there an existing class a group of these parameters belongs to? Search wider than the file that fired: values that keep appearing side by side are the entity, and it is usually one of the domain's own nouns — where that name already exists, it is the answer.
2. If not, create it — then move behaviour that uses those fields onto it.
3. If one object owns most of the parameters, it may be the natural home for this function/method.
4. Use it at every site it fits, not only the one that fired — a call passing three of its fields is the same concept sitting under the threshold.

Useful tip: rewrite each call site with the signature that feels natural there, and let that shape the final function/method.

**AVOID**: A `{ ...everything }` bag that merely renames the list hides the coupling instead of removing it. A `FooProps` or options object named after the function/method that takes it is the same bag: organised by function/method rather than by abstraction, so the next function/method invents another one and the concept stays unnamed. You are done when the entity carries a domain name and no call site still passes its fields loose.

{% include "includes/line_level_issues.md" %}