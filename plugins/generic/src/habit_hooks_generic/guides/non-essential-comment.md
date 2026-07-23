Comments indicate code that is not self-documenting. The smell is the *need* for the comment — the reader could not work out what the code does from the names and structure alone.

Extract complex logic into well-named functions instead of explaining with a comment. A function called `applyDiscountForLoyalCustomers` does not need a header explaining what it does.

Remove comments unless they impact functionality (executable annotations) or explain *why* something non-obvious was chosen (a workaround for a specific library bug, a reference to a spec). Comments that explain *what* the code does are almost always redundant — or worse, drift out of sync with the code and start lying.

Do not delete an `eslint-disable` or shebang on autopilot — those are flagged separately and exempted from this rule.

{% include "includes/line_level_issues.md" %}
