from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(r"^\[project\]\n(.*?)(?=^\[|\Z)", text, re.S | re.M)
    assert project, "pyproject.toml has no [project] table"
    found = re.search(r'^version = "([^"]+)"$', project.group(1), re.M)
    assert found, "[project] has no version"
    return found.group(1)


def test_plugin_manifest_version_is_the_package_version():
    # Claude Code keys its plugin cache on this string: while it stays the same, an installed
    # copy never updates, however many commits land.
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest.get("version") == project_version()


def test_marketplace_entries_do_not_carry_another_version():
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    for entry in marketplace["plugins"]:
        assert entry.get("version", project_version()) == project_version(), entry["name"]
