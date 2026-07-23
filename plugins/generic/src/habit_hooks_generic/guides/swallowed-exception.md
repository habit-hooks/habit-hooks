A catch-all that discards the error is hiding a failure you have not understood, not handling one you planned for. Name the specific error you expect here and why — that sentence is usually the fix.

**Make the failure visible:**
1. Catch only what you can name: the specific error type the call can really raise. If you cannot name it, you are guessing — let everything else surface where it can be seen.
2. Make the decision explicit: recover, or add context and rethrow, or — at a boundary that must stay alive (request handler, worker loop, CLI entry point) — log the full stack trace and continue. Logging and returning a default is a real option when it is a decision, not a reflex.

Useful tip: ask "if this fires at 3am, will anyone know it happened, and know why?" If not, it is still a swallow, however it is dressed up. If you are unsure whether a catch is a decision or a reflex, check with a human.

**AVOID**: narrowing the type or adding a suppression comment just to quiet the checker while the error is still discarded.

{% include "includes/line_level_issues.md" %}
