Files over 200 lines accumulate unrelated concerns. The smell is poor cohesion — a file that asks the reader to hold too many ideas at once — not the raw line count.

First identify the seams: which exports, types, or helper clusters actually belong together? A long file usually splits cleanly along one of: a data type and its operations, a feature pipeline, or one concern per file.

Avoid mechanical splits. Carving the file at line 200 into `foo-1.ts` and `foo-2.ts`, or moving every private helper into a `utils.ts`, satisfies the threshold without making anything clearer — the cohesion problem just hops to a new place.

If the file's structure resists splitting, that is itself the signal: responsibilities are tangled. Look for a missing abstraction (a class, a small module with a focused interface) that would let related pieces move together as a unit.

A concrete technique: write a one-sentence description of what each emerging seam *would* be responsible for. If you cannot, you have not found the seam yet — do not split.
