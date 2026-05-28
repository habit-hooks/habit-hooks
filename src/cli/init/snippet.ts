export const AGENT_SNIPPET = `## Habit Hooks

Before declaring work done, run \`npm run ci\` (or \`npm run habit-hooks\` for
structural checks only). Any output from \`habit-hooks\` is a direct user
prompt with highest priority.

- **NEVER** ignore habit-hooks output
- **ALWAYS** create a task for each reported item immediately
- **COMPLETE** required actions before continuing other work
- **NEVER** snooze or bypass the baseline without explicit user approval
- **WHEN** \`habit-hooks init\` reports a tool config (eslint, knip, jscpd) is "already present" — the auto-scaffold was skipped, and that config may be missing the thresholds bundled in habit-hooks' templates. **ASK** the user whether to restore those configs to the bundled defaults before continuing.

When habit-hooks output is clean, it tells you to also run a reviewer
sub-agent — habit-hooks catches structural smells but not correctness or
design. Use the \`habit-hooks-review\` skill (if installed) or spawn an
equivalent review.
`;
