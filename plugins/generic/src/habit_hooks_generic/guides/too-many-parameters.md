High parameter count is a sign of coupling.
Parameters that travel together across several calls are a missing abstraction.

**Find the missing abstraction:**
1. Look at the call sites and nearby functions — is there an existing class a group of these parameters belongs to?
2. If not, create it — then move behaviour that uses those fields onto it.
3. If one object owns most of the parameters, it may be the natural home for this function.

Useful tip: rewrite each call site with the signature that feels natural there, and let that shape the final method. 

**AVOID**: A `{ ...everything }` bag that merely renames the list hides the coupling instead of removing it.

{% include "includes/line_level_issues.md" %}