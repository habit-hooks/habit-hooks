
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .errors import SpecError
from .glyphs import FAIL, PASS
from .markdown import Block, Heading, Marker, read_elements
from .steps import Command, CopyFile, Screen, SetEnv, Stderr, Stdin, WriteFile


@dataclass
class SpecCase:
    name: str
    skip: bool
    steps: list[object]
    continued: bool = False
    inherited_steps: int = 0


def _exit_code(arg: str) -> int | None:
    fail = re.search(FAIL + r"\s*(\d+)", arg)
    if fail:
        return int(fail.group(1))
    return 0 if PASS in arg else None


def _file_step(arg: str) -> tuple[object, bool | None]:
    arg = arg.strip()
    if "@" in arg:
        dst, src = (p.strip() for p in arg.split("@", 1))
        return CopyFile(dst or src, src), None
    return WriteFile(arg), True


def build_marker(marker: Marker) -> tuple[object, bool | None]:
    kind, arg = marker.kind, marker.arg
    if kind == "file":
        return _file_step(arg)
    if kind == "env":
        return SetEnv(arg.strip()), True
    if kind == "stdin":
        return Stdin(), True
    if kind == "screen":
        return Screen(_exit_code(arg) or 0), False
    return Stderr(_exit_code(arg)), False  # kind == "stderr"


class StepBuilder:

    def __init__(self):
        self.steps: list[object] = []
        self.pending: tuple[object, bool] | None = None  # (step, fence_required)

    def build(self, elements: list[object]) -> list[object]:
        for element in elements:
            self._feed(element)
        self._flush()
        return self.steps

    def _feed(self, element: object) -> None:
        if isinstance(element, Marker):
            self._on_marker(element)
        elif isinstance(element, Block):
            self._on_block(element)

    def _on_marker(self, marker: Marker) -> None:
        self._flush()
        step, fence = build_marker(marker)
        if fence is None:
            self.steps.append(step)
        else:
            self.pending = (step, fence)

    def _on_block(self, block: Block) -> None:
        if block.is_command:
            self._flush()
            self.steps.append(Command(block.content))
        elif self.pending is not None:  # a bare fence with no owning marker is cosmetic
            self.pending[0].block = block.content
            self.steps.append(self.pending[0])
            self.pending = None

    def _flush(self) -> None:
        if self.pending is None:
            return
        step, required = self.pending
        if required:
            raise SpecError(f"marker {step!r} has no code block")
        self.steps.append(step)
        self.pending = None


@dataclass
class _Node:
    level: int
    skip: bool
    parent: "_Node | None"
    name: str
    elements: list[object] = field(default_factory=list)
    has_child: bool = False


class TreeBuilder:

    def __init__(self):
        self.nodes: list[_Node] = []
        self.stack: list[_Node] = []  # current ancestry, by increasing heading level

    def build(self, elements: list[object]) -> list[_Node]:
        for element in elements:
            self._feed(element)
        return self.nodes

    def _feed(self, element: object) -> None:
        if isinstance(element, Heading):
            self._open(element)
        elif self.stack:
            self.stack[-1].elements.append(element)

    def _open(self, heading: Heading) -> None:
        while self.stack and self.stack[-1].level >= heading.level:
            self.stack.pop()
        parent = self.stack[-1] if self.stack else None
        node = _Node(heading.level, heading.skip, parent, heading.text)
        if parent is not None:
            parent.has_child = True
        self.nodes.append(node)
        self.stack.append(node)


def _ancestry(leaf: _Node) -> list[_Node]:
    chain: list[_Node] = []
    node: _Node | None = leaf
    while node is not None:
        chain.append(node)
        node = node.parent
    chain.reverse()
    return chain


def _leaf_case(leaf: _Node) -> SpecCase:
    chain = _ancestry(leaf)
    inherited = [step for node in chain[:-1] for step in StepBuilder().build(node.elements)]
    own = StepBuilder().build(leaf.elements)
    return SpecCase(
        leaf.name,
        any(n.skip for n in chain),
        inherited + own,
        "(continued)" in leaf.name,
        len(inherited),
    )


def parse_spec(text: str) -> list[SpecCase]:
    nodes = TreeBuilder().build(read_elements(text))
    return [_leaf_case(node) for node in nodes if not node.has_child]
