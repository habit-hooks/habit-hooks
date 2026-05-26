# Prompt review checklist

This file is not shipped with the npm package. Use it when adding or editing prompts.

## Every prompt

- [ ] Conveys the **purpose** of the rule (what smell it catches, why it matters) — not just a restatement of the threshold.
- [ ] Guides **analysis before action** ("First identify…", "Ask…").
- [ ] Warns against **mechanical fixes** that satisfy the rule without addressing the smell.
- [ ] Offers a **non-obvious approach** for the hard cases (the "if you are stuck, try this" door).
- [ ] Reads as guidance an agent would internalise as a *habit*, not a checkbox to clear.

## Word-count targets

- **Tier 1** (architectural smells): ≤ 150 words. Rich, with all four bullets above.
- **Tier 2** (code hygiene): 30–60 words. Purpose + one warning is usually enough.
- **Tier 3** (TS advisories): 30–60 words.

## Common failure modes

- "This function is over 12 lines, please make it shorter." — pure restatement.
- "Extract a helper function." — mechanical, no analysis prompt.
- "Add `// eslint-disable-next-line`" — never suggest suppression in a prompt.
- All-caps `CRITICAL:` prefix — the reporter already renders framing; do not duplicate it in the prompt body.
