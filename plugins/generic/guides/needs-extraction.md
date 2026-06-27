This file is **both** oversized and duplicated. Those two signals together point at one fix, and it is not "split the file in half."

When a long file also repeats a block, the length is usually a *symptom*: the file has accreted a concept that wants its own home, and the duplication is that concept leaking out in two places. Splitting the file at the line threshold would scatter the duplication further; deduplicating in place would leave the bloated file just as incohesive. Do both at once, in the right order.

Read the duplicated block first and name what it does in one sentence. That sentence is the missing module: extract the duplicated block into a shared unit (a small module, a class, a value object) with a focused interface — not a five-parameter helper that merely hides the lines.

Then let that extraction *carry weight out of the file*. Move the related types and helpers that belong with the new abstraction along with it. Re-check the file size afterwards: a good extraction usually brings the file back under the threshold on its own, because the thing you pulled out was the reason it was too big.

If the two copies are genuinely different ideas that only look alike, do not force a shared abstraction — extract along the real seams instead, and if the duplication is the lesser evil, snooze it with a note rather than distorting either side.
