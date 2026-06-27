A null check — and especially a `!` — is usually covering an underlying design problem, not handling a value that's legitimately sometimes-missing. Before you write one, say out loud what the null actually represents and how it relates to the other objects. That sentence almost always names the real fix.

Two design smells hide behind most null assertions:

- **A circular dependency with no clear owner.** Two objects reference each other, so neither can be built first and one sits briefly null. The fix is to give the dependency a direction: work out which object owns the other (operates on its state, is its exclusive consumer) and have the owner *create* the owned so they're initialised together — or, if it's really an upward event, give the emitter an opaque handler (no-op default) that the owner wires after construction. The mutual reference disappears.
- **Null standing in for a special case** — "outside the grid", "not found", "not loaded yet". Model that case explicitly: a subclass or a separate class with the same interface — a null object, like a `NullCell` that behaves as a blocked cell — resolved once at the boundary so no caller ever sees null.

Sometimes a null genuinely is unavoidable. Even then `!` is wrong: it swallows the failure at runtime. Replace it with an explicit check — an `if`-guard / early return, or a throw with a clear message — so a broken assumption fails loudly, where it happens.

The only exception: an extremely simple method where the nullable's scope is tiny, a wrong value genuinely cannot cause a silent error, and there's a real performance gain. This should be vanishingly rare — check in with a human before settling for it.
