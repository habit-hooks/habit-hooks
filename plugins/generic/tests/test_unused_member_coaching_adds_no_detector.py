"""A shared guide does not make generic a producer of the smell."""

from __future__ import annotations

from pathlib import Path

from plugin_fixture import loader_for, write_project_config


def test_generic_declares_no_unused_member_detector(tmp_path: Path) -> None:
    write_project_config(tmp_path, 'plugins = ["generic"]')

    plugin = loader_for(tmp_path).load_plugin("generic")

    assert [sensor.name for sensor in plugin.sensors] == ["line-count", "jscpd"]
