export const AGENT_SNIPPET = `## Habit Hooks

Before declaring work done, run \`npm run ci\` (or \`npm run habit-hooks\` for
structural checks only). Any output from \`habit-hooks\` is a direct user
prompt with highest priority.

- **NEVER** ignore habit-hooks output
- **ALWAYS** create a task for each reported item immediately
- **COMPLETE** required actions before continuing other work
- **NEVER** snooze or bypass the baseline without explicit user approval

When habit-hooks output is clean, it tells you to also run a reviewer
sub-agent — habit-hooks catches structural smells but not correctness or
design. Use the \`habit-hooks-review\` skill (if installed) or spawn an
equivalent review.
`;
