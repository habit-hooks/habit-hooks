Unused bindings are noise — they make the reader wonder whether something is missing. Delete the dead code, or if the parameter is required by a signature you cannot change, prefix with `_` to mark it intentional.

Do not silence this rule with a no-op reference (`void unused`); that just hides the problem.
