# habit-hooks-php

The PHP Habit Hooks plugin: wraps [`phpmd`](https://phpmd.org/) for structural
code-smell detection. `phpmd` ships bundled as a phar, so nothing beyond a PHP
runtime is required.

## Install

```sh
pip install "habit-hooks[php]"
```

## Enable

```toml
# .habit-hooks/config.toml
plugins = ["php", "generic"]
```

Installing a plugin does not switch it on — it has to be named in
`plugins` before habit-hooks runs it.

## Detectors

- `php` — `brew install php` (nothing else; phpmd ships bundled)

Part of [habit-hooks](https://github.com/habit-hooks/habit-hooks).
