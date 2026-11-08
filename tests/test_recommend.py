
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from habit_hooks.recommend import PluginStatus, recommendations, used_languages
from habit_hooks.resolve import Resolver
from plugin_fixture import write_plugin

INSTALL_AND_ENABLE = (
    "habit-sensors: detected python; consider `pip install habit-hooks-python`, "
    'then add "python" to `plugins` in .habit-hooks/config.toml'
)
ENABLE_ONLY = (
    "habit-sensors: detected python; the python plugin is installed but not "
    'enabled — add "python" to `plugins` in .habit-hooks/config.toml'
)


def _on_hand(*plugins: str) -> Callable[[str], bool]:
    return lambda name: name in plugins


def _hints(project_dir: Path, plugins: PluginStatus) -> list[str]:
    return recommendations(project_dir, ["src/app.py"], plugins)


def test_an_uninstalled_plugin_is_named_with_both_steps(tmp_path: Path) -> None:
    assert _hints(tmp_path, PluginStatus(set(), _on_hand())) == [INSTALL_AND_ENABLE]


def test_an_installed_but_unenabled_plugin_is_told_to_enable_it(tmp_path: Path) -> None:
    assert _hints(tmp_path, PluginStatus(set(), _on_hand("python"))) == [ENABLE_ONLY]


def test_an_active_language_is_not_recommended(tmp_path: Path) -> None:
    assert _hints(tmp_path, PluginStatus({"python"}, _on_hand("python"))) == []


def test_an_unused_language_is_not_recommended(tmp_path: Path) -> None:
    assert (
        recommendations(tmp_path, ["src/app.cbl"], PluginStatus(set(), _on_hand()))
        == []
    )


def test_a_java_project_is_recommended_java(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert recommendations(tmp_path, [], PluginStatus(set(), _on_hand())) == [
        "habit-sensors: detected java; "
        "consider `pip install habit-hooks-java`, "
        'then add "java" to `plugins` in .habit-hooks/config.toml'
    ]

    (tmp_path / "pom.xml").unlink()
    (tmp_path / "build.gradle.kts").write_text("", encoding="utf-8")
    assert recommendations(tmp_path, [], PluginStatus(set(), _on_hand())) != []
    assert recommendations(tmp_path, [], PluginStatus({"java"}, _on_hand("java"))) == []
    assert recommendations(tmp_path, ["src/App.java"], PluginStatus(set(), _on_hand())) != []


def test_a_ruby_project_is_recommended_ruby(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    assert recommendations(tmp_path, [], PluginStatus(set(), _on_hand())) == [
        "habit-sensors: detected ruby; "
        "consider `pip install habit-hooks-ruby`, "
        'then add "ruby" to `plugins` in .habit-hooks/config.toml'
    ]

    (tmp_path / "Gemfile").unlink()
    (tmp_path / ".rubocop.yml").write_text("", encoding="utf-8")
    assert recommendations(tmp_path, [], PluginStatus(set(), _on_hand())) != []
    assert recommendations(tmp_path, [], PluginStatus({"ruby"}, _on_hand("ruby"))) == []
    assert recommendations(tmp_path, ["app/billing.rb"], PluginStatus(set(), _on_hand())) != []


def test_a_file_inside_a_dependency_directory_names_no_language(tmp_path: Path) -> None:
    files = [
        "node_modules/pkg/index.php",
        "vendor/legacy/app.php",
        "site-packages/dep/mod.py",
        ".venv/lib/dep.py",
        "venv/lib/dep.py",
    ]

    assert used_languages(tmp_path, files) == []


def test_a_real_source_file_alongside_dependency_files_names_its_language(
    tmp_path: Path,
) -> None:
    assert used_languages(tmp_path, ["node_modules/pkg/index.php", "src/app.php"]) == [
        "php"
    ]


def test_a_root_config_file_names_its_language_despite_dependency_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "composer.json").write_text("{}", encoding="utf-8")

    assert used_languages(tmp_path, ["node_modules/pkg/index.php"]) == ["php"]


def test_a_vendored_plugin_counts_as_installed(tmp_path: Path) -> None:
    write_plugin(tmp_path, "python", {"config.toml": 'language = "python"'})
    resolver = Resolver.discover(tmp_path)
    assert resolver.has_plugin("python")
    assert _hints(tmp_path, PluginStatus(set(), resolver.has_plugin)) == [ENABLE_ONLY]
