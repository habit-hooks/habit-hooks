# habit-hooks-typescript

The TypeScript Habit Hooks plugin: wraps
[`eslint`](https://eslint.org/) and [`knip`](https://knip.dev/) for structural
and dead-code smells, plus a [`ts-morph`](https://ts-morph.com/)-backed comment
sensor.

## Install

```sh
pip install "habit-hooks[typescript]"
```

## Enable

```toml
# .habit-hooks/config.toml
plugins = ["typescript", "generic"]
```

Installing a plugin does not switch it on — it has to be named in
`plugins` before habit-hooks runs it.

## Detectors

- `node`, [`eslint`](https://eslint.org/), [`knip`](https://knip.dev/),
  [`ts-morph`](https://ts-morph.com/) — `npm install --save-dev eslint knip ts-morph`
  (`node` from your system package manager, e.g. `brew install node`)

A project with no eslint config of its own needs
`@typescript-eslint/parser` and `@typescript-eslint/eslint-plugin` too, since
habit-hooks then lints with the config it ships.

Part of [habit-hooks](https://github.com/habit-hooks/habit-hooks).
