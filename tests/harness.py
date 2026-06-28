"""Test harness that runs the executable specs (``docs/**/*.spec.md``).

This is dev/test tooling for building habit-hooks, not shipped product code.
The grammar is defined by ``docs/executable_spec.md`` — that file is the
contract. Markers are matched by base codepoint; any U+FE0F variation selector
is ignored.

Run the unit tests with ``uv run pytest``; run the specs themselves with
``uv run python tests/harness.py [docs/foo.spec.md ...]`` (defaults to every
``docs/**/*.spec.md``).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

# Marker base codepoints (U+FE0F stripped before matching).
_FILE = "\U0001F4C4"  # 📄
_STDIN = "⌨"  # ⌨️
_SCREEN = "\U0001F5A5"  # 🖥️
_STDERR = "\U0001F6A8"  # 🚨
_ENV = "✏"  # ✏️
_SKIP = "\U0001F7E1"  # 🟡
_PASS = "✅"  # ✅
_FAIL = "❌"  # ❌

_MARKERS = {_FILE: "file", _ENV: "env", _STDIN: "stdin", _SCREEN: "screen", _STDERR: "stderr"}
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class SpecError(Exception):
    """A spec is malformed (a parse-time problem)."""


class SpecFailure(Exception):
    """A test assertion failed or a step errored at run time."""


def normalize(text: str) -> str:
    """Strip ANSI, trim trailing whitespace per line, drop trailing blanks."""
    lines = [line.rstrip() for line in _ANSI.sub("", text).split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


# --- Execution context -----------------------------------------------------


class Context:
    """Mutable state shared by a single test's steps as they run."""

    def __init__(self, workdir: Path, repo_root: Path):
        self.workdir = workdir
        self.repo_root = repo_root
        self.env = dict(os.environ)
        self.stdin: str | None = None
        self.last: subprocess.CompletedProcess[str] | None = None
        self.exit_checked = False

    def require_last(self, marker: str) -> subprocess.CompletedProcess[str]:
        if self.last is None:
            raise SpecError(f"{marker} assertion with no preceding command")
        return self.last

    def check_default_exit(self) -> None:
        """A command with no explicit exit assertion must still have exited 0."""
        if self.last is not None and not self.exit_checked and self.last.returncode != 0:
            raise SpecFailure(f"command exited {self.last.returncode}, expected 0\n{self.last.stderr}")

    def assert_stream(self, name: str, actual: str, expected: str | None) -> None:
        if expected is not None and normalize(actual) != normalize(expected):
            raise SpecFailure(
                f"{name} mismatch\n--- expected ---\n{normalize(expected)}\n"
                f"--- actual ---\n{normalize(actual)}"
            )


# --- Steps (each knows how to apply itself) --------------------------------


@dataclass
class WriteFile:
    path: str
    block: str | None = None  # the file's content, filled when its fence is paired

    def apply(self, c: Context) -> None:
        dest = c.workdir / self.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.block + "\n")


@dataclass
class CopyFile:
    dst: str
    src: str

    def apply(self, c: Context) -> None:
        dest = c.workdir / self.dst
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((c.repo_root / self.src).read_bytes())


@dataclass
class SetEnv:
    var: str
    block: str | None = None

    def apply(self, c: Context) -> None:
        c.env[self.var] = self.block


@dataclass
class Stdin:
    block: str | None = None

    def apply(self, c: Context) -> None:
        c.stdin = self.block + "\n"


@dataclass
class Command:
    script: str

    def apply(self, c: Context) -> None:
        c.check_default_exit()
        c.last = subprocess.run(
            ["bash", "-c", self.script],
            cwd=c.workdir,
            env=c.env,
            input=c.stdin,
            capture_output=True,
            text=True,
        )
        c.stdin = None
        c.exit_checked = False


@dataclass
class Screen:
    exit_code: int
    block: str | None = None  # expected stdout

    def apply(self, c: Context) -> None:
        result = c.require_last("🖥️")
        c.exit_checked = True
        if result.returncode != self.exit_code:
            raise SpecFailure(f"exit {result.returncode}, expected {self.exit_code}\n{result.stderr}")
        c.assert_stream("stdout", result.stdout, self.block)


@dataclass
class Stderr:
    exit_code: int | None = None
    block: str | None = None  # expected stderr

    def apply(self, c: Context) -> None:
        result = c.require_last("🚨")
        if self.exit_code is not None:
            c.exit_checked = True
            if result.returncode != self.exit_code:
                raise SpecFailure(f"exit {result.returncode}, expected {self.exit_code}")
        c.assert_stream("stderr", result.stderr, self.block)


@dataclass
class SpecCase:
    name: str
    skip: bool
    steps: list[object]


# --- Markdown elements -----------------------------------------------------


@dataclass
class Heading:
    level: int
    text: str
    skip: bool


@dataclass
class Marker:
    kind: str
    arg: str


@dataclass
class Block:
    info: str
    content: str

    @property
    def is_command(self) -> bool:
        # ```bash is reserved for commands and never consumed as a marker payload.
        head = self.info.split()
        return bool(head) and head[0] == "bash"


def _heading(node: SyntaxTreeNode) -> Heading:
    text = node.children[0].content.rstrip()
    skip = text.replace("️", "").rstrip().endswith(_SKIP)
    return Heading(int(node.tag[1]), text, skip)


def _markers(text: str) -> list[Marker]:
    """Every marker line in a paragraph (one paragraph may hold several)."""
    lines = (line.lstrip() for line in text.split("\n"))
    return [Marker(_MARKERS[head[0]], head[1:].replace("️", "")) for head in lines if head and head[0] in _MARKERS]


def _elements(text: str) -> list[object]:
    """Markdown → the ordered Heading/Marker/Block elements we care about."""
    root = SyntaxTreeNode(MarkdownIt("commonmark").parse(text))
    elements: list[object] = []
    for node in root.children:
        if node.type == "heading":
            elements.append(_heading(node))
        elif node.type == "fence":
            elements.append(Block(node.info.strip(), node.content.rstrip("\n")))
        elif node.type == "paragraph":
            elements.extend(_markers(node.children[0].content))
    return elements


# --- Building steps from markers -------------------------------------------


def _exit_code(arg: str) -> int | None:
    fail = re.search(_FAIL + r"\s*(\d+)", arg)
    if fail:
        return int(fail.group(1))
    return 0 if _PASS in arg else None


def _build_marker(marker: Marker) -> tuple[object, bool | None]:
    """Return (step, block) where block is None=no fence, True=required, False=optional."""
    kind, arg = marker.kind, marker.arg
    if kind == "file":
        arg = arg.strip()
        if "@" in arg:
            dst, src = (p.strip() for p in arg.split("@", 1))
            return CopyFile(dst or src, src), None
        return WriteFile(arg), True
    if kind == "env":
        return SetEnv(arg.strip()), True
    if kind == "stdin":
        return Stdin(), True
    if kind == "screen":
        return Screen(_exit_code(arg) or 0), False
    return Stderr(_exit_code(arg)), False  # kind == "stderr"


def _build_steps(elements: list[object]) -> list[object]:
    """Pair markers with their payload fences for one context's direct elements."""
    steps: list[object] = []
    pending: tuple[object, bool] | None = None  # (step, fence_required)

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        step, required = pending
        if required:
            raise SpecError(f"marker {step!r} has no code block")
        steps.append(step)
        pending = None

    for el in elements:
        if isinstance(el, Marker):
            flush()
            step, needs = _build_marker(el)
            if needs is None:
                steps.append(step)
            else:
                pending = (step, needs)
        elif isinstance(el, Block):
            if el.is_command:
                flush()
                steps.append(Command(el.content))
            elif pending is not None:
                pending[0].block = el.content
                steps.append(pending[0])
                pending = None
            # else: a bare fence with no owning marker is cosmetic — ignore.
    flush()
    return steps


# --- Parsing into test cases -----------------------------------------------


@dataclass
class _Node:
    level: int
    skip: bool
    parent: "_Node | None"
    name: str
    elements: list[object] = field(default_factory=list)
    has_child: bool = False


def _ancestry(node: _Node) -> list[_Node]:
    chain: list[_Node] = []
    while node is not None:
        chain.append(node)
        node = node.parent
    chain.reverse()
    return chain


def parse_spec(text: str) -> list[SpecCase]:
    """Return the leaf test cases, each with its full inherited step list."""
    nodes: list[_Node] = []
    stack: list[_Node] = []  # current ancestry, by increasing heading level
    for el in _elements(text):
        if isinstance(el, Heading):
            while stack and stack[-1].level >= el.level:
                stack.pop()
            parent = stack[-1] if stack else None
            node = _Node(el.level, el.skip, parent, el.text)
            if parent is not None:
                parent.has_child = True
            nodes.append(node)
            stack.append(node)
        elif stack:
            stack[-1].elements.append(el)

    tests: list[SpecCase] = []
    for node in nodes:
        if node.has_child:
            continue  # only leaf contexts are tests
        chain = _ancestry(node)
        steps = [step for anc in chain for step in _build_steps(anc.elements)]
        tests.append(SpecCase(node.name, any(n.skip for n in chain), steps))
    return tests


def execute(test: SpecCase, workdir: Path, repo_root: Path) -> None:
    """Run a test's steps in ``workdir``. Raise on any assertion failure."""
    context = Context(workdir, repo_root)
    for step in test.steps:
        step.apply(context)
    context.check_default_exit()


# --- Discovery & runner (CLI) ----------------------------------------------


@dataclass
class Result:
    file: Path
    name: str
    status: str  # "pass" | "skip" | "fail"
    message: str = ""


def discover(root: Path) -> list[Path]:
    return sorted(root.glob("docs/**/*.spec.md"))


def run_test(test: SpecCase, path: Path, repo_root: Path) -> Result:
    if test.skip:
        return Result(path, test.name, "skip")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            execute(test, Path(tmp), repo_root)
        except (SpecFailure, SpecError) as exc:
            return Result(path, test.name, "fail", str(exc))
    return Result(path, test.name, "pass")


def run_file(path: Path, repo_root: Path) -> list[Result]:
    return [run_test(test, path, repo_root) for test in parse_spec(path.read_text())]


_GLYPH = {"pass": "✅", "skip": "🟡", "fail": "❌"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path.cwd()
    files = sorted(Path(a) for a in argv) if argv else discover(root)
    if not files:
        print(f"no docs/**/*.spec.md under {root}")
        return 1

    counts = {"pass": 0, "skip": 0, "fail": 0}
    for path in files:
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"\n{rel}")
        for result in run_file(path, root):
            counts[result.status] += 1
            print(f"  {_GLYPH[result.status]} {result.name}")
            if result.status == "fail":
                for line in result.message.splitlines():
                    print(f"      {line}")

    print(f"\n{counts['pass']} passed, {counts['skip']} skipped, {counts['fail']} failed")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
