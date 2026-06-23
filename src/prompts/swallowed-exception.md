A broad `except` (`except:`, `except Exception`, `except BaseException`) that swallows the error is hiding a failure you have not understood, not handling one you planned for. Before writing it, name the specific error you expect here and why. That sentence is usually the fix.

Catch only the exception you actually expect: `ValueError`, `KeyError`, `TimeoutError`, whatever the call can really raise. If you cannot name it, you are guessing, and every other error should stay free to surface where it can be seen.

Then do something real: recover, or add context and re-raise (`raise ... from err`), or let it propagate. Catching broadly and then `pass`, logging-and-continuing, or returning a default is the swallow. The bug does not disappear. It resurfaces later, far from here, where it costs the most.

Narrowing the type or adding `# noqa` only to quiet the checker is not a fix if the error is still discarded. The smell is the silent swallow, not the width of the catch.

One legitimate case: a top-level boundary that must stay alive (a request handler, a worker loop, a CLI entry point). Even there, catch as narrow as you can, log the full traceback, and never discard the error silently. If unsure, check with a human first.
