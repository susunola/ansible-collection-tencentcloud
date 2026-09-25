# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/check_module_options.py.

The rule caught a real defect -- ``ckafka_topic`` declared ``tags`` and never
sent it -- so the cases pinned here are the shapes that decision rests on: an
option read through an imported helper counts, a nested sub-option consumed by
a generic mapper is out of scope, a single-choice constant has nothing to
read, and a spec dict stored in a variable is not mistaken for a mapping of
option names.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_module_options.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_module_options",
                                                  SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def options():
    return _load_script()


@pytest.fixture
def tree(options, tmp_path, monkeypatch):
    """Point the script at a throwaway collection tree."""
    (tmp_path / "plugins" / "modules").mkdir(parents=True)
    (tmp_path / "plugins" / "module_utils").mkdir(parents=True)
    monkeypatch.setattr(options, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(options, "MODULES_DIR", tmp_path / "plugins" / "modules")
    return tmp_path


def _write(tree, source, name="demo.py", directory="modules"):
    path = tree / "plugins" / directory / name
    path.write_text(source, encoding="utf-8")
    return path


READ = '    module = {"topic_name": p["topic_name"]}\n'


def test_a_read_option_passes(options, tree):
    _write(tree,
           "def run_module(p):\n"
           '    spec = {"topic_name": {"type": "str"}}\n'
           + READ)
    assert options.findings() == []


def test_a_declared_option_nothing_reads_is_reported(options, tree):
    """The shape of the real defect: ``tags`` in the spec, nowhere else."""
    _write(tree,
           "def run_module(p):\n"
           '    spec = {"topic_name": {"type": "str"},\n'
           '            "tags": {"type": "dict", "default": {}}}\n'
           + READ.replace("topic_name", "topic_name"))
    problems = options.findings()
    assert len(problems) == 1
    assert "tags" in problems[0]
    assert "no code path reads it" in problems[0]


def test_an_option_read_by_an_imported_helper_passes(options, tree):
    """``cos.resolve_appid(module)`` reads ``appid`` inside the helper."""
    _write(tree,
           "from ansible_collections.susunola.tencentcloud.plugins."
           "module_utils.cos import resolve_appid\n"
           "def run_module(module):\n"
           '    spec = {"appid": {"type": "str"}}\n'
           "    return resolve_appid(module)\n")
    _write(tree, 'def resolve_appid(module):\n'
                 '    return module.params.get("appid")\n',
           name="cos.py", directory="module_utils")
    assert options.findings() == []


def test_a_nested_sub_option_is_out_of_scope(options, tree):
    """A generic mapper renames sub-option keys, so no literal read exists."""
    source = "\n".join([
        "def run_module(p):",
        '    spec = {"vpcs": {"type": "list", "elements": "dict",',
        '                     "options": {"vpc_id": {"required": True}}}}',
        "    return _items(p['vpcs'])",
        "",
    ])
    _write(tree, source)
    assert options.findings() == []


def test_a_single_choice_option_is_a_constant(options, tree):
    _write(tree,
           "def run_module(p):\n"
           '    spec = {"state": {"choices": ["absent"], "default": "absent"}}\n')
    assert options.findings() == []


def test_a_reused_spec_dict_is_not_a_mapping_of_options(options, tree):
    """``rule = {"type": "dict", "options": {...}}`` is a spec, not options."""
    _write(tree,
           "RULE = {'type': 'dict', 'options': {'port': {'type': 'str'}}}\n"
           "def run_module(p):\n"
           '    spec = {"port": {"type": "str"}}\n'
           '    value = p["port"]\n'
           "    return value\n")
    assert options.findings() == []


def test_a_multi_choice_option_still_needs_a_read(options, tree):
    _write(tree,
           "def run_module(p):\n"
           '    spec = {"state": {"choices": ["present", "absent"],\n'
           '                       "default": "present"}}\n')
    problems = options.findings()
    assert len(problems) == 1
    assert "'state'" in problems[0]


def test_check_exits_non_zero_on_a_finding(options, tree):
    _write(tree,
           "def run_module(p):\n"
           '    spec = {"tags": {"type": "dict"}}\n')
    out, err = io.StringIO(), io.StringIO()
    rc = options.main(["--check"], out=out, err=err)
    assert rc == 1
    assert "findings (1)" in out.getvalue()
    assert "must be one the module reads" in err.getvalue()


def test_committed_modules_read_every_declared_option(options):
    """The repository must pass, not just the fixture."""
    assert options.findings() == []
