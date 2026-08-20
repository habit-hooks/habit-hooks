# habit-hooks-python

The Python Habit Hooks plugin: wraps [`ruff`](https://docs.astral.sh/ruff/) for
structural smells (complexity, too many parameters, swallowed exceptions, …)
and [`deptry`](https://github.com/fpgmaas/deptry) for dependency issues.

## Install

```sh
pip install "habit-hooks[python]"
```

## Enable

```toml
# .habit-hooks/config.toml
plugins = ["python", "generic"]
```

Installing a plugin does not switch it on — it has to be named in
`plugins` before habit-hooks runs it.

## Detectors

- [`ruff`](https://docs.astral.sh/ruff/), [`deptry`](https://github.com/fpgmaas/deptry) —
  `pip install ruff deptry`

Part of [habit-hooks](https://github.com/habit-hooks/habit-hooks).
