A broad `except` (`except:`, `except Exception`, `except BaseException`) that discards the error silently is hiding a failure you have not understood, not handling one you planned for. Before you write it, name the specific error you expect and why. That one sentence is usually the fix.

Work through it in order:

1. **Catch only what you can name.** `ValueError`, `KeyError`, `TimeoutError`, whatever the call really raises. If you cannot name it, you are guessing, and every other error should stay free to surface where someone can see it.
2. **Make the decision visible.** Recover from it, add context and re-raise (`raise ... from err`), or, at a boundary that has to stay alive, log the full traceback (`logging.exception(...)`) and continue. Logging and returning a default is a real option, not automatically a swallow.
3. **The test is not whether you re-raised.** Ask one question: if this fires at 3am, will anyone know it happened, and will they know why? What turns a catch into a swallow is doing it blindly: a wide catch, no named error, nothing logged, the failure gone without a trace. If the answer is no, it is still a swallow, however you dressed it up.

Narrowing the type or adding `# noqa` only to quiet ruff is not a fix if the error is still discarded.

If you are unsure whether this catch is a real decision or a reflex, check with a human before you keep it.

{% include "includes/line_level_issues.md" %}
