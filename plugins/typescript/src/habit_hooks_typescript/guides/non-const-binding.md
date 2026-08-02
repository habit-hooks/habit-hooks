A `let` that is never reassigned tells the reader a lie of omission: `let` is a promise that the value *will* change, so every reader who meets this binding has to scan the rest of the scope to find the reassignment — and there isn't one. That wasted vigilance is the cost, and it compounds, because it trains readers to stop trusting `let` to mean anything.

Change it to `const`. Now the binding says what's true: this name points at one value for its whole life, and no reader has to look for a reassignment that never comes. If flipping to `const` turns out to break — because the value *is* reassigned on a path you'd forgotten — that's the tool doing you a favour: keep `let`, and the reassignment it just revealed is exactly the state change worth being conscious of.

Done right, `const` is the default and `let` is the exception, so the mere sight of `let` flags the handful of bindings that genuinely mutate.

{% include "includes/line_level_issues.md" %}
