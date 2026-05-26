An unused class member is dead weight: either delete it or wire it up. There is no third option that does not lie to a future reader.

Delete by default. If the member is part of a planned-but-unbuilt API, document that in code with `@public`/`@internal` JSDoc tags so knip can be configured to ignore it — do not leave the dead code naked.

If you find yourself wanting to keep the member "just in case", that is a signal you have not committed to a direction. Pick one: delete it now, or write the test that exercises it so it stops being unused.

A concrete technique: search the codebase for the method name. If the only hit is the definition itself, the method is genuinely dead. If there are hits in tests but no production caller, the test is testing the test — delete both.
