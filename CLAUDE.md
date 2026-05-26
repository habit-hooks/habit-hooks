# habit-hooks notes

## Gotchas

### ESLint v10 rejects files outside its `basePath`

When running ESLint programmatically against fixtures or test repos that
live outside the project root, you'll see "File ignored because outside of
base path". Pass `cwd` explicitly to the `ESLint` constructor so its
`basePath` matches where the files actually live. `eslintCheck.run` takes
an optional `cwd` for this reason; the runner always supplies one.

### Plugin scope in flat config

When using ESLint flat config programmatically, a `plugins` block declared
only on a `files`-scoped config object is NOT in scope for a separate `rules`
block. To use `@typescript-eslint/...` rules in a rules block, declare the
plugin on the same config object that defines the rules (or repeat it).

### TS plugin probe — don't import statically

`@typescript-eslint/eslint-plugin` must be loaded via dynamic `import()`
after `require.resolve('@typescript-eslint/eslint-plugin', { paths: [cwd] })`
succeeds. Importing statically pulls it into our hard dep tree; the probe
keeps it optional and lets us fail open when the consumer's project doesn't
have it. The probe result is cached per cwd.

### JSDoc nodes are not MultiLineCommentTrivia in ts-morph

`/** ... */` blocks are `SyntaxKind.JSDoc` (321) when attached to a
declaration, NOT `MultiLineCommentTrivia`. To find them, query both. See
`src/checks/comment-check.ts`.

### jscpd ESM build has a broken `colors/safe` import

`jscpd@4.2.4`'s ESM output imports `"colors/safe"` without the `.js`
extension, which Node's strict ESM resolver rejects. Load it via
`createRequire` to get the CJS build instead — see `src/checks/jscpd-check.ts`.

### knip's `exports` field omits the bin path

`knip@5.88.1` exports only `.` and `./session`, so
`require.resolve('knip/bin/knip.js')` fails. We resolve `'knip'` (main entry)
and navigate up to `../bin/knip.js`. See `src/checks/knip-check.ts`.

### knip needs `package.json` in cwd

Running knip in a directory without `package.json` exits 2 with a help
message. `knipCheck` skips silently when no `package.json` is present —
the user's project always has one, but our internal test temp dirs
often don't.

### knip 6.x removed `classMembers` issue type

We pin `knip@5.88.1` because v6 dropped detection of unused class members.
If knip 6 ever re-introduces it (or if we move to a different unused-member
strategy), revisit `src/checks/knip-check.ts` and the version pin.

### Runner file discovery doesn't honour project ignores

`runner.discoverFiles` uses fast-glob with a hardcoded ignore set
(`node_modules`, `dist`, `coverage`). Fixtures under `tests/fixtures/**`
get linted when you run `node dist/cli.js` against the repo root —
that's why a smoke run on our own source shows fixture violations. The
fix lives in a future phase (probably the `init` command or a config
field like `discovery.exclude`).
