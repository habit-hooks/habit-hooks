Duplicated blocks are the cheapest visible sign of a missing abstraction. The right fix is rarely "extract a helper" — it's usually to name the concept that both copies are reaching for.

Read both occurrences side by side and ask: (1) Are these two copies of the same idea, or two different ideas that happen to look alike? (2) If they are the same idea, what is its name? (3) Does the duplicated block belong to a domain concept that does not exist yet — a value object, a strategy, a small class?

Avoid mechanical extraction. Pulling the matching lines into a function with five parameters and a couple of conditionals leaves the real shape untouched and adds a worse name on top. If extracting feels awkward, the underlying abstraction is wrong — step back and find the right one.

A concrete technique: try to write one sentence that names what both copies do. If the sentence reads naturally, that sentence is the name of the abstraction you are missing. If you can only describe the block as "the code that does X, Y, and Z", the duplication is hiding two or three smaller abstractions, not one.

If the two copies actually diverge in important ways and a shared abstraction would distort either side, document the decision (a short note or a test that pins both behaviours) and snooze the duplication — duplication is the lesser evil compared to a wrong abstraction.

These blocks are duplicated:

{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.startLine }}-{{ issue.details.endLine }}
{% endfor %}
