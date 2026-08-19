"""The consumer projects the installed-wheel gate points an installed run at.

What a project has in it is half of every case here: a plugin's helper can only
be proved to reach the project's own tools by a project that really has them, so
these lay out a symlinked ``node_modules`` where a consumer would have run
``npm install`` rather than stubbing one. Each config names the one plugin under
test and switches off the sensors whose tools that project has no reason to own,
so a case fails for the packaging it is about and nothing else.

Kept beside ``test_installed_wheel_smoke``, which is then only what an installed
run must produce.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TYPESCRIPT_PLUGIN = REPO_ROOT / "plugins" / "typescript"

OVERSIZED_LINES = 205
MAX_ALLOWED_LINES = 200

# The manifest a TypeScript project is scaffolded with today. A CommonJS helper
# that lands in this scope dies on its first line (#112), so the gate asks about
# packaging from inside the declaration that answered it wrong.
ESM_MANIFEST = '{ "name": "demo", "version": "0.0.0", "type": "module" }\n'

TYPESCRIPT_SOURCE = "src/helper.ts"
PYTHON_SOURCE = "billing.py"
PHP_SOURCE = "billing.php"
JAVA_SOURCE = "Billing.java"


def _project(tmp_path: Path, name: str, config: str) -> Path:
    project = tmp_path / name
    (project / ".habit-hooks").mkdir(parents=True)
    (project / ".habit-hooks" / "config.toml").write_text(config)
    return project


def oversized_project(tmp_path: Path, name: str) -> Path:
    """A project whose only smell is one file over the line-count threshold."""
    project = _project(
        tmp_path,
        name,
        'plugins = ["generic"]\n'
        'files = ["**/*.py"]\n\n'
        "[sensors.jscpd]\n"
        "disabled = true\n",
    )
    lines = "".join(f"x{n} = 0\n" for n in range(1, OVERSIZED_LINES + 1))
    (project / "big.py").write_text(lines)
    return project


def java_project(tmp_path: Path) -> Path:
    """A project whose one file pmd has three things to say about."""
    project = _project(tmp_path, "java-proj", 'plugins = ["java"]\n')
    (project / JAVA_SOURCE).write_text(
        "import java.io.File;\n"
        "import java.io.IOException;\n"
        "class Billing {\n"
        "    double charge(double a, double b, double c, double d, double e) {\n"
        "        int dead = 1;\n"
        "        return a + b + c + d + e;\n"
        "    }\n"
        "}\n"
    )
    return project


def php_project(tmp_path: Path) -> Path:
    """A project whose one file phpmd has two things to say about."""
    project = _project(tmp_path, "php-proj", 'plugins = ["php"]\n')
    (project / PHP_SOURCE).write_text(
        "<?php\n"
        "function charge($a, $b, $c, $d, $e, $f, $g, $h, $i, $j, $k) {\n"
        "    $unused = 1;\n"
        "    return $a + $b + $c + $d + $e + $f + $g + $h + $i + $j + $k;\n"
        "}\n"
    )
    return project


def typescript_project(tmp_path: Path) -> Path:
    """A TypeScript project carrying one comment that restates its code, and the
    Node tools a consumer's ``npm install`` would have left in it.

    eslint and knip are off because this case is about the comment sensor's
    helper: a project with no config of its own for either tool would fail the
    run for reasons that say nothing about packaging.
    """
    project = _project(
        tmp_path,
        "typescript-proj",
        'plugins = ["typescript"]\n\n'
        "[sensors.eslint]\n"
        "disabled = true\n\n"
        "[sensors.knip]\n"
        "disabled = true\n",
    )
    (project / "src").mkdir()
    (project / "package.json").write_text(ESM_MANIFEST)
    (project / "node_modules").symlink_to(TYPESCRIPT_PLUGIN / "node_modules")
    (project / TYPESCRIPT_SOURCE).write_text(
        "export function used(): void {\n"
        "  // this comment restates what the code already says clearly\n"
        "}\n"
    )
    return project


def python_project(tmp_path: Path) -> Path:
    """A Python project whose only smell is a variable ruff can see is unused.

    deptry is off: it reads a dependency manifest this project has none of, so
    it would fail the run without ever exercising the packaging under test.
    """
    project = _project(
        tmp_path,
        "python-proj",
        'plugins = ["python"]\n\n[sensors.deptry]\ndisabled = true\n',
    )
    (project / PYTHON_SOURCE).write_text(
        "def total(items):\n    unused = 1\n    return sum(items)\n"
    )
    return project
