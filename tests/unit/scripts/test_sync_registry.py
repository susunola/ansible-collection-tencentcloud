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
    return modules_dir, runtime


def test_script_path_exists():
    assert SCRIPT_PATH.exists()


def test_discover_modules_sorted_and_skips_dunder(sync, tmp_path):
    _write_module(tmp_path, "b_info")
    _write_module(tmp_path, "a")
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    assert sync.discover_modules(tmp_path) == ["a", "b_info"]


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


def test_main_writes_then_check_passes(sync, tmp_path, monkeypatch, capsys):
    modules_dir, runtime = _fake_repo(tmp_path)
    monkeypatch.setattr(sync, "MODULES_DIR", modules_dir)
    monkeypatch.setattr(sync, "RUNTIME_YML", runtime)

    assert sync.main(["--check"]) == 1
    assert sync.main([]) == 0
    assert sync.main(["--check"]) == 0

    runtime_text = runtime.read_text(encoding="utf-8")
    assert "    - subnet\n" in runtime_text
    assert "# Deprecation process" in runtime_text

    # A newly added module makes the registry stale again.
    _write_module(modules_dir, "eip")
    assert sync.main(["--check"]) == 1
    assert "stale registries" in capsys.readouterr().err
    assert sync.main([]) == 0
    assert "    - eip\n" in runtime.read_text(encoding="utf-8")


def test_real_registries_are_up_to_date(sync):
    module_names = sync.discover_modules(sync.MODULES_DIR)
    runtime = sync.RUNTIME_YML.read_text(encoding="utf-8")
    assert sync.render_runtime_yml(runtime, module_names) == runtime, \
        "run scripts/sync_registry.py"
