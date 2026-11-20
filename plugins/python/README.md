# habit-hooks-python

[Habit Hooks](https://github.com/habit-hooks/habit-hooks) turns best-practice coding advice into AI habits: it runs your linters, then replaces each raw rule violation with a short coaching guide an AI coding agent can act on. This package is its Python plugin.

## What it does

The plugin enables `habit-sensors` over a Python project and rewrites four tools' findings into structural code smells from the [canonical vocabulary](https://github.com/habit-hooks/habit-hooks/blob/main/docs/smell-vocabulary.md):

- **ruff** — `too-many-parameters`, `high-complexity`, `unused-variable`, `unused-import`, `swallowed-exception`. Unmapped codes pass through under their own name rather than disappearing.
- **deptry** — dependencies declared but never imported.
- **comment analysis** — comments and docstrings that narrate instead of stating a non-obvious why, coached as `non-essential-comment`.
- **pytest** — runs the test files in scope with `pytest --durations=0` and flags tests whose setup, call and teardown together exceed a 1 second budget (overridable with `[sensors.slow-test] args = ["--budget", "2"]`), coached as `slow-test`. Timings come from pytest report hooks, not captured terminal text: quiet output, `--no-summary`, and text printed by tests cannot hide or forge them.

A tool that crashes fails the run rather than reporting clean.

## Requirements

- Python 3.11+
- [ruff](https://docs.astral.sh/ruff/), [deptry](https://github.com/fpgmaas/deptry) and [pytest](https://pytest.org/) on `PATH` (`pip install ruff deptry pytest`).

## Installation

The plugin ships as an extra of the core package:

```bash
pip install "habit-hooks[python]"
```

Then list it in `.habit-hooks/config.toml` at the repo root:

```toml
plugins = ["python", "generic"]
```

The full walk-through — init, running, snoozing, CI — is in the [core README](https://github.com/habit-hooks/habit-hooks#readme).

## Slow-test scope and timing

The sensor runs only Python test files in the Habit Hooks scope, using the project's `python_files` patterns (including custom names), pytest configuration and installed plugins. A change to application code or `conftest.py` alone does not select dependent tests; use `--all` to check all tracked test files. When the project enables `--doctest-modules`, scoped Python modules are also checked for doctests. Each scan executes tests again, so their side effects and runtime still apply.

Setup, call and teardown durations are summed at pytest's native precision; only the displayed time is rounded. The comparison is strictly greater than the budget, not greater than or equal. Pytest attributes shared fixture setup and teardown to the tests that perform them, not evenly across the suite. Repeated or rerun executions of the same node ID use the slowest attempt, not the sum of retries; distinct parametrized IDs remain separate. Node IDs retain pytest's escaping, so literal backslashes and Unicode parameter IDs are not reinterpreted.

Empty, deselected and skipped suites can legitimately produce no findings. Collection errors, missing timing data, and pytest crashes fail the scan instead of reporting clean. `--collect-only` and `--setup-only` are refused because they do not measure test execution. Selection options such as `-k`, `--lf`, and `-x` are respected, so only executed tests are measured. Custom collectors and plugins that replace pytest's normal setup/call/teardown reports are not supported; they must supply normal duration reports for measured tests.
