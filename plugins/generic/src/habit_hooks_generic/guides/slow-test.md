Slow tests hide the cost of work that should happen once, or of luck that should be a fixture. The smell is not the clock; it is a test that does too much, rebuilds expensive state, or hunts through random seeds instead of asserting a known case.

Work through it in order:

1. **Cut per-test work.** Keep each test on one behaviour. Setup, I/O, and waits that are not the behaviour under test belong outside the example, or out of the suite.
2. **Reuse fixtures instead of rebuilding expensive state.** A database, a rendered tree, or a compiled fixture that several tests need should be built once and shared (or frozen) rather than reconstructed in every example. Share immutable setup or reset mutable state between tests so reuse does not couple their outcomes.
3. **Make the test deterministic.** Seed randomness. Freeze the fixture you care about and assert that case, rather than asserting over many random seeds and hoping a slow search eventually hits the interesting one.

A sleep, a larger timeout, or deleting the assertion to sneak under the budget is not a fix. The test should be fast because it does less, and reliable because its input is known.

Tests over {{ details.maxAllowed }} seconds:

{% for issue in issues -%}
{{ issue.details.test }}  {{ issue.details.content }}
{% endfor -%}
