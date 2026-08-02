Two import statements pulling from the same module is a small thing that reliably grows into a confusing one: the second import is easy to miss, so the two drift — one gets a name the other lacks, an edit updates one and not the other, and a reader can no longer trust the top of the file to list what comes from where.

Merge them into a single statement that names everything this module takes from that source. If the split was deliberate — a type-only import kept separate from a value import — that intent is worth keeping, but say it with the language's own type-import syntax, not two plain imports that look accidental.

Done right, each module appears exactly once in the import list, and that one line is the whole truth about what this file borrows from it.

{% include "includes/line_level_issues.md" %}
