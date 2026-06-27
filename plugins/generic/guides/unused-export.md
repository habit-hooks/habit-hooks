An export nothing in production reaches is one of two things, and they have opposite fixes. Decide which before you touch it.

**Dead code** — nothing uses it, tests included. Delete it, along with anything that only existed to support it. Don't keep it "just in case"; version control remembers.

**Reached only by tests** — production never calls it, but a test does. The export exists to let the test see an internal. That is not allowed: it couples the test to the implementation and makes the module's public surface lie. Drive the behaviour through the real entry point instead, so the test exercises it the way production does. If the logic is substantial enough to deserve its own focused test, that is the signal it wants to be its **own class or module** — extract it, and the tested method becomes a legitimate public member of the new unit, not a back door punched into this one.

Either way the export goes away. The wrong move is to silence the report by adding the file to knip's entry list or snoozing it — that just preserves the leak. The only real exception is a genuine public API surface that knip can't see is consumed (a published package entry); make that explicit in knip's `entry`/config, not by ignoring the smell.
