"""Every catalogued smell must ship a real coaching guide.

The product's value is the coaching. A smell in ``catalogue.DEFAULT_SEVERITY``
with no ``guides/<smell>.md`` falls through to the one-size ``uncoached.md``,
silently degrading the product. This test turns that gap into a build failure so
it cannot reopen (#101).

It routes each smell through the mapper's real ``_resolve_guide`` against the
full installed plugin set, exactly as a live run would, and asserts the resolved
guide is not the uncoached fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from habit_hooks import mapper
from habit_hooks.catalogue import DEFAULT_SEVERITY, UNCOACHED_GUIDE
from habit_hooks.config import Config, load_config
from habit_hooks.resolve import Resolver, installed_plugin_dirs
from plugin_fixture import write_project_config


@dataclass(frozen=True)
class Routing:
    """The mapper's guide routing for the full installed plugin set."""

    config: Config
    resolver: Resolver

    @classmethod
    def full_plugin_set(cls, project_dir: Path) -> Routing:
        plugins = sorted(installed_plugin_dirs())
        write_project_config(project_dir, f"plugins = {plugins!r}")
        return cls(load_config(project_dir), Resolver.discover(project_dir))

    @property
    def languages(self) -> list[str | None]:
        """Every language a finding can route under: ``None`` and each plugin's."""
        return [None, *sorted(set(self.config.plugin_languages.values()))]

    def guide_for(self, smell: str, language: str | None) -> str:
        finding = {"smell": smell, "language": language, "details": {}, "issues": []}
        return mapper._resolve_guide(finding, self.config, self.resolver).name


@pytest.mark.parametrize("smell", sorted(DEFAULT_SEVERITY))
def test_every_catalogue_smell_resolves_to_a_guide(smell: str, tmp_path: Path) -> None:
    routing = Routing.full_plugin_set(tmp_path)
    resolved = {lang: routing.guide_for(smell, lang) for lang in routing.languages}
    coached = {lang: name for lang, name in resolved.items() if name != UNCOACHED_GUIDE}
    assert coached, (
        f"catalogued smell {smell!r} renders {UNCOACHED_GUIDE} for every language "
        f"({sorted(resolved)}) — ship a guides/{smell}.md in the plugin it belongs to"
    )


def test_unused_variable_resolves_for_python_and_typescript_not_just_php(
    tmp_path: Path,
) -> None:
    """``unused-variable`` is language-agnostic — it fires from ruff F841 and
    eslint no-unused-vars, not just PHPMD — so its guide must live in ``generic``
    where every language's routing reaches it (#101)."""
    routing = Routing.full_plugin_set(tmp_path)
    for language in ("python", "typescript"):
        assert (
            routing.guide_for("unused-variable", language) != UNCOACHED_GUIDE
        ), f"unused-variable renders {UNCOACHED_GUIDE} for a {language} finding"
