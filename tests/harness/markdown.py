
from __future__ import annotations

from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from .glyphs import MARKERS, SKIP

CONTINUED = "(example continued from previous section)"


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
        head = self.info.split()
        return bool(head) and head[0] == "bash"


def _heading(node: SyntaxTreeNode) -> Heading:
    text = node.children[0].content.rstrip()
    skip = text.replace("️", "").rstrip().endswith(SKIP)
    return Heading(int(node.tag[1]), text, skip)


def _markers(text: str) -> list[Marker]:
    lines = (line.lstrip() for line in text.split("\n"))
    return [Marker(MARKERS[h[0]], h[1:].replace("️", "")) for h in lines if h and h[0] in MARKERS]


def read_elements(text: str) -> list[object]:
    root = SyntaxTreeNode(MarkdownIt("commonmark").parse(text))
    elements: list[object] = []
    for node in root.children:
        if node.type == "heading":
            elements.append(_heading(node))
        elif node.type == "fence":
            elements.append(Block(node.info.strip(), node.content.rstrip("\n")))
        elif node.type == "paragraph":
            content = node.children[0].content
            if content.strip() == CONTINUED:
                elements.append(Marker("continued", ""))
            else:
                elements.extend(_markers(content))
    return elements
