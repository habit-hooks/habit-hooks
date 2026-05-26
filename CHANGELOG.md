# Changelog

## Unreleased (v2 wrap pivot)
- Foundation: tool detection helper, shell-out wrapper, prompts-by-rule-id registry. No behavioural change yet — these scaffolds future-phase wraps.
- `RunResult.stderr` field added; populated as `[]` in this phase, future phases will fill it with wrapped-tool warnings.
