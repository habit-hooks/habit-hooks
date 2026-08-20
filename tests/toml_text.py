"""Escape arbitrary text for embedding in a TOML basic string.

A fixture that interpolates a path into an f-string bound for a ``.toml``
file hits TOML's own escaping the moment that path holds a backslash: a
Windows ``sys.executable`` or ``tmp_path`` breaks the parse exactly the way
an unescaped quote would (``Unescaped '\\' in a string``), because backslash
is TOML's escape character too. ``toml_string`` escapes the same way
``tomli_w`` does for any string value, so a fixture never has to reason about
what characters a host path happens to contain.
"""

from __future__ import annotations


def toml_string(text: str) -> str:
    """A TOML basic string literal for ``text``, quotes included."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
