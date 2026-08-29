A block that has grown past a dozen lines almost always has more than one responsibility, and that is the smell to chase, not the line count itself.

Analyse responsibilities first: what distinct concerns does this block handle? Do these concerns belong in methods? Is the block a candidate for a method on a class?

Find true responsibility boundaries rather than splitting at the threshold: `apply_part_one` / `apply_part_two` carved off to fit the line count is one responsibility wearing two names.

A concrete technique: write what the block does in one short sentence and refactor until the code reads as close to it as possible. If you cannot say what it does in one sentence, it almost certainly does more than one thing.

{% include "includes/line_level_issues.md" %}
