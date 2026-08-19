# habit-hooks-java

The Java Habit Hooks plugin: wraps [`pmd`](https://pmd.github.io/) for
structural code-smell detection.

## Install

```sh
pip install "habit-hooks[java]"
```

## Enable

```toml
# .habit-hooks/config.toml
plugins = ["java", "generic"]
```

Installing a plugin does not switch it on — it has to be named in
`plugins` before habit-hooks runs it.

## Detectors

- [`pmd`](https://pmd.github.io/) — `brew install pmd` (it brings its own Java runtime)

Part of [habit-hooks](https://github.com/habit-hooks/habit-hooks).
