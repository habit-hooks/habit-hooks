A `type` or `interface` exported with no consumer is either internal-by-accident or an undeclared public type surface. Either way the keyword lies: it tells readers "something outside this module depends on this shape", when nothing does.

Ask first: is this type part of a deliberate public API? Return-types and option-bags that flow through an exported function, types re-exported from a package entry, types consumed by a downstream plugin or framework — these are real public surface knip just cannot see. The fix is configuration: add the file (or the symbol's containing entry) to `entry` in `knip.json` so the tool stops asking.

Otherwise the type is internal-by-accident. Drop the `export` keyword. The type stays — it is still used inside its own module — it just stops pretending to be part of the module's public surface. If a test was importing the type directly, that usually means the test is reaching past the public API; move the test to the same module, or assert against the function's inferred return type instead.

Avoid mechanical fixes. Re-exporting the type from `index.ts` to satisfy knip does not address the smell; it just makes the implicit public surface look intentional. Suppressing the rule per-symbol scatters the public-API decision across the codebase instead of capturing it in one config file.

A concrete technique: for each flagged type, ask "if I remove the `export` keyword, what breaks?" If nothing breaks, the export was a lie. If something outside the module breaks, you have just discovered an undocumented public type — write it down in `knip.json` and treat that file as a public-API surface from now on.
