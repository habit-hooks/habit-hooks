#!/usr/bin/env node

const message = `
habit-hooks is no longer distributed on npm.

It has been rewritten in Python and is now published on PyPI.
Please uninstall the npm package and reinstall from one of the options below.

Install options:

  uv (recommended):   uv tool install habit-hooks
    one-off:          uvx habit-hooks

  pipx:               pipx install habit-hooks

  pip:                pip install habit-hooks

  Homebrew:           brew install habit-hooks/tap/habit-hooks

The default install includes the core plus the language-agnostic "generic"
plugin. Language plugins are opt-in extras:

  habit-hooks[python]
  habit-hooks[typescript]
  habit-hooks[php]
  habit-hooks[all]

Project: https://github.com/habit-hooks/habit-hooks
`;

process.stderr.write(message);
process.exit(1);
