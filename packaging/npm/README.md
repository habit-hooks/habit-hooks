# habit-hooks (deprecated on npm)

**habit-hooks is no longer distributed on npm.** It has been rewritten in
Python and is now published on [PyPI](https://pypi.org/project/habit-hooks/).

Please uninstall the npm package and reinstall from one of the options below.

## Install options

- **uv (recommended):** `uv tool install habit-hooks`
  (one-off run: `uvx habit-hooks`)
- **pipx:** `pipx install habit-hooks`
- **pip:** `pip install habit-hooks`
- **Homebrew:** `brew install habit-hooks/tap/habit-hooks`

The default install includes the core plus the language-agnostic `generic`
plugin. Language plugins are opt-in extras:

- `habit-hooks[python]`
- `habit-hooks[typescript]`
- `habit-hooks[php]`
- `habit-hooks[all]`

Project: https://github.com/habit-hooks/habit-hooks
