from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync_registry.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("sync_registry", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sync():
    return _load_script()


FAKE_MODULE = """\
#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: {name}
short_description: {desc}
'''
"""

RUNTIME_YML = """\
---
requires_ansible: \">=2.16.0\"
action_groups:
  all:
    - vpc
    - vpc_info

# Deprecation process: modules and plugins are deprecated by adding a
# plugin_routing.deprecation entry for them.
plugin_routing: {}
"""

README_MD = """\
# Collection

Resource modules:

| Module | Purpose |
| --- | --- |
| `vpc` | old description |

Read-only `_info` modules:

| Module | Purpose |
| --- | --- |
| `vpc_info` | old description |

Hand-written note about generated modules.

## Included plugins

| Plugin | Type | Purpose |
| --- | --- | --- |
| `tencentcloud_cvm` | inventory | old plugin row |
"""

GALAXY_YML = """\
namespace: susunola
name: tencentcloud
version: 1.0.0
description: "Demo collection. 3 modules (resource modules plus _info facts modules) cover things."
"""


def _write_module(modules_dir, name, desc=None):
    modules_dir.mkdir(parents=True, exist_ok=True)
    desc = desc or "Manage %s" % name
    (modules_dir / (name + ".py")).write_text(
        FAKE_MODULE.format(name=name, desc=desc), encoding="utf-8")


def _fake_repo(tmp_path):
    modules_dir = tmp_path / "plugins" / "modules"
    _write_module(modules_dir, "vpc")
    _write_module(modules_dir, "subnet")
    _write_module(modules_dir, "vpc_info")
    (tmp_path / "meta").mkdir(parents=True)
    runtime = tmp_path / "meta" / "runtime.yml"
    runtime.write_text(RUNTIME_YML, encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text(README_MD, encoding="utf-8")
    galaxy = tmp_path / "galaxy.yml"
    galaxy.write_text(GALAXY_YML, encoding="utf-8")
    return modules_dir, runtime, readme, galaxy


def test_script_path_exists():
    assert SCRIPT_PATH.exists()


def test_discover_modules_sorted_and_skips_dunder(sync, tmp_path):
    _write_module(tmp_path, "b_info")
    _write_module(tmp_path, "a")
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    assert sync.discover_modules(tmp_path) == ["a", "b_info"]


def test_split_modules(sync):
    write, info = sync.split_modules(["a_info", "b", "security_group_rule", "c_info"])
    assert write == ["b", "security_group_rule"]
    assert info == ["a_info", "c_info"]


def test_short_description(sync, tmp_path):
    _write_module(tmp_path, "vpc", "Manage Tencent Cloud VPCs")
    assert sync.short_description(tmp_path / "vpc.py") == "Manage Tencent Cloud VPCs"


def test_short_description_missing_block(sync, tmp_path):
    path = tmp_path / "empty.py"
    path.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no DOCUMENTATION block"):
        sync.short_description(path)


def test_render_runtime_yml_preserves_surroundings(sync):
    rendered = sync.render_runtime_yml(RUNTIME_YML, ["subnet", "vpc", "vpc_info"])
    assert rendered == RUNTIME_YML.replace(
        "    - vpc\n", "    - subnet\n    - vpc\n")
    assert 'requires_ansible: ">=2.16.0"' in rendered
    assert "# Deprecation process" in rendered
    assert "plugin_routing: {}" in rendered


def test_render_runtime_yml_requires_action_groups(sync):
    with pytest.raises(ValueError, match="action_groups"):
        sync.render_runtime_yml("---\nrequires_ansible: \">=2.16.0\"\n", [])


def test_render_readme_replaces_both_tables(sync):
    rendered = sync.render_readme(
        README_MD,
        [sync.module_row("subnet", "Manage subnets"), sync.module_row("vpc", "Manage VPCs")],
        [sync.module_row("vpc_info", "Query VPCs")],
    )
    assert "| `subnet` | Manage subnets |\n| `vpc` | Manage VPCs |\n" in rendered
    assert "| `vpc_info` | Query VPCs |\n" in rendered
    # The note paragraph, section headers and the plugins table survive.
    assert "Hand-written note about generated modules." in rendered
    assert "| Plugin | Type | Purpose |" in rendered
    assert "| `tencentcloud_cvm` | inventory | old plugin row |" in rendered
    assert "old description" not in rendered


def test_render_readme_requires_two_module_tables(sync):
    with pytest.raises(ValueError, match="expected exactly two"):
        sync.render_readme("# no tables\n", [], [])


def test_main_writes_then_check_passes(sync, tmp_path, monkeypatch, capsys):
    modules_dir, runtime, readme, galaxy = _fake_repo(tmp_path)
    monkeypatch.setattr(sync, "MODULES_DIR", modules_dir)
    monkeypatch.setattr(sync, "RUNTIME_YML", runtime)
    monkeypatch.setattr(sync, "README_MD", readme)
    monkeypatch.setattr(sync, "GALAXY_YML", galaxy)

    assert sync.main(["--check"]) == 1
    assert sync.main([]) == 0
    assert sync.main(["--check"]) == 0

    runtime_text = runtime.read_text(encoding="utf-8")
    assert "    - subnet\n" in runtime_text
    assert "# Deprecation process" in runtime_text
    readme_text = readme.read_text(encoding="utf-8")
    assert "| `subnet` | Manage subnet |" in readme_text
    assert "Hand-written note about generated modules." in readme_text
    # The fake repo has 3 modules; the count in the galaxy description is
    # rewritten in place, without duplicating the "modules" wording.
    assert "3 modules (resource modules" in galaxy.read_text(encoding="utf-8")

    # A newly added module makes every registry stale again.
    _write_module(modules_dir, "eip")
    assert sync.main(["--check"]) == 1
    assert "stale registries" in capsys.readouterr().err
    assert sync.main([]) == 0
    assert "    - eip\n" in runtime.read_text(encoding="utf-8")
    assert "4 modules (resource modules" in galaxy.read_text(encoding="utf-8")


def test_render_galaxy_yml_rewrites_count_without_duplication(sync):
    rendered = sync.render_galaxy_yml(GALAXY_YML, ["a", "b"])
    assert "2 modules (resource modules" in rendered
    assert "modules modules" not in rendered


def test_real_registries_are_up_to_date(sync):
    module_names = sync.discover_modules(sync.MODULES_DIR)
    write_names, info_names = sync.split_modules(module_names)
    descriptions = {
        name: sync.short_description(sync.MODULES_DIR / (name + ".py"))
        for name in module_names
    }
    runtime = sync.RUNTIME_YML.read_text(encoding="utf-8")
    assert sync.render_runtime_yml(runtime, module_names) == runtime, \
        "run scripts/sync_registry.py"
    readme = sync.README_MD.read_text(encoding="utf-8")
    rendered = sync.render_readme(
        readme,
        [sync.module_row(name, descriptions[name]) for name in write_names],
        [sync.module_row(name, descriptions[name]) for name in info_names],
    )
    assert rendered == readme, "run scripts/sync_registry.py"
