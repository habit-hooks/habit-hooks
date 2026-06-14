A fatal message means ESLint could not analyse the file at all, so every other rule went unchecked there too — real issues in this file are currently invisible.

Typical causes worth checking: a syntax error, a missing or misconfigured `tsconfig.json`, a plugin version mismatch, or a config that fails to import. Re-run the single file with `npx eslint <file>` to see the full stack the JSON output hides.

You've fixed it when a deliberate change to the file produces the ordinary lint error or warning you'd expect — that proves analysis is running again. Do not silence it with `eslint-disable` or by dropping the file from the lint set.
