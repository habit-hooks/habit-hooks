This code is unused in production. The only thing keeping it alive is a test that references it — so knip's default pass, which counts the test as a real user, never flagged it, and only the `--production` pass caught it. That makes it more dangerous than plainly dead code, not less: it looks covered, and a reviewer reads the passing test as proof it earns its place.

It does not. A test that exercises code nothing in production reaches is testing a thing that does not happen. There are exactly two honest fixes, and you have to decide which:

**The code should not exist.** Nothing real needs it. Delete the code **and the test** — deleting only the code leaves a test that no longer compiles, and deleting only the test leaves the same dead code you started with, now with nothing pointing at it. Both go, together. Don't keep either "just in case"; version control remembers.

**The code should be wired up.** The behaviour is wanted, and the test is telling you it was never connected to a real entry point. Connect it — call it from the code path that should have called it all along — so production reaches it and the test exercises it the way production does. The finding disappears because the code stops being test-only, not because you hid it.

The move to avoid: making the test-only reference "count" by adding the file or export to knip's production `entry`/config. That silences the report and preserves exactly the lie it caught — code that ships but only a test ever runs.

If the logic genuinely deserves its own focused test, that is the signal it wants to be its **own module**, tested through its own public surface — not a back door left open in this one.

{% include "includes/file_level_issues.md" %}
