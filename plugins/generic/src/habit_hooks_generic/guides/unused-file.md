Nothing in the project imports this file — no production code, no test, no entry point reaches it. That is more expensive than it looks: every reader who opens it has to work out whether it matters, tooling still parses and type-checks it, and a search for "where is this used" keeps landing on a dead end.

Decide which of two things it is. If it is genuinely dead — a module orphaned by a refactor that moved its callers elsewhere — delete it, along with anything that existed only to support it. Version control remembers it; you do not need to keep it "just in case". If it is *meant* to be reachable — a real entry point, a published package export, a script an outside process invokes that the tool can't see — then the file isn't the problem, the missing connection is: wire it to the entry point that should have reached it, or declare it as an entry in the tool's config so the analysis knows it is a root. Do not silence the finding by ignoring the path; that just hides the orphan.

Done right, every file in the tree is reachable from a real root, and "unused" means deleted, not muted.

{% include "includes/file_level_issues.md" %}
