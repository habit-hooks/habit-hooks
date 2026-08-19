# habit-hooks-generic

The language-agnostic Habit Hooks plugin: a built-in line-count sensor plus a
jscpd-backed duplication sensor, for any project regardless of language.

## Install

This plugin ships as part of the core — installing `habit-hooks` installs it,
nothing extra to add.

```sh
pip install habit-hooks
```

## Enable

```toml
# .habit-hooks/config.toml
plugins = ["generic"]
```

Installing a plugin does not switch it on — it has to be named in
`plugins` before habit-hooks runs it.

## Detectors

- [`jscpd`](https://github.com/kucherenko/jscpd) — `npm install --save-dev jscpd`
- The line counter is built in; nothing to install for it.

Part of [habit-hooks](https://github.com/habit-hooks/habit-hooks).
