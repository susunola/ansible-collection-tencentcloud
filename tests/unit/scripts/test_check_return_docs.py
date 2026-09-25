# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/check_return_docs.py.

A RETURN block is a promise a playbook branches on. The two ways it can be
wrong are the two directions this check reads: a key the module returns and
never documents, and a key it documents and never returns. Both are pinned
here, along with the one case the check deliberately cannot judge.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_return_docs.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_return_docs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def returns():
    return _load_script()


@pytest.fixture
def tree(tmp_path, returns, monkeypatch):
    """Point the census at a throwaway module directory."""
    modules = tmp_path / "plugins" / "modules"
    modules.mkdir(parents=True)
    monkeypatch.setattr(returns, "MODULES_DIR", str(modules))
    return tmp_path


def write_module(tree, name, body):
    (tree / "plugins" / "modules" / ("%s.py" % name)).write_text(body, encoding="utf-8")


DOC = """DOCUMENTATION = r'''
module: demo
options: {}
'''

RETURN = r'''
%s'''

def run_module():
    module = TencentCloudModule()
    %s
"""


def module(return_body, exit_call):
    return DOC % (return_body, exit_call)


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_return_docs_pass(returns, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["check_return_docs.py", "--check"])
    assert returns.main() == 0


def test_no_findings_in_the_repository(returns):
    assert returns.findings() == []


# --------------------------------------------------------------------------
# a key returned and never documented
# --------------------------------------------------------------------------

def test_undocumented_return_key_is_reported(tree, returns):
    """cvm_instance returned count, instances and terminated in exact_count
    mode and documented only instance."""
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n",
        "module.exit_json(changed=True, widget={}, count=3)"))
    assert returns.findings() == [
        ("demo", "returns count, which RETURN does not document")]


def test_documented_key_is_accepted(tree, returns):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n",
        "module.exit_json(changed=True, widget={})"))
    assert returns.findings() == []


def test_ansible_builtin_keys_need_no_entry(tree, returns):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n",
        "module.exit_json(changed=True, msg='ok', widget={})"))
    assert returns.findings() == []


def test_return_block_missing_is_reported(tree, returns):
    write_module(tree, "demo",
                 "DOCUMENTATION = r'''\nmodule: demo\n'''\n\n"
                 "def run_module():\n    module.exit_json(changed=True)\n")
    assert returns.findings() == [("demo", "has no RETURN block")]


# --------------------------------------------------------------------------
# a key documented and never returned
# --------------------------------------------------------------------------

def test_documented_but_never_returned_is_reported(tree, returns):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n"
        "ghost:\n  description: Never returned.\n  returned: never\n  type: str\n",
        "module.exit_json(changed=True, widget={})"))
    assert returns.findings() == [
        ("demo", "documents ghost, which the module never returns")]


def test_a_splat_disables_the_reverse_check_only(tree, returns):
    """**diff carries keys the check cannot read, so a module that splats is
    not asked why it documents one it does not name."""
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n"
        "ghost:\n  description: Maybe from the splat.\n  returned: always\n  type: str\n",
        "module.exit_json(changed=True, **(diff or {}), widget={})"))
    assert returns.findings() == []


# --------------------------------------------------------------------------
# the shape of a return entry
# --------------------------------------------------------------------------

def test_entry_without_a_type_is_reported(tree, returns):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n",
        "module.exit_json(changed=True, widget={})"))
    assert returns.findings() == [("demo", "widget has no type")]


def test_nested_entry_without_returned_is_reported(tree, returns):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n"
        "  contains:\n    id:\n      description: Its id.\n      type: str\n",
        "module.exit_json(changed=True, widget={})"))
    assert returns.findings() == [("demo", "widget.contains.id has no returned")]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_main_check_reports_the_count(tree, returns, capsys):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n",
        "module.exit_json(changed=True, widget={})"))
    assert returns.main(["--check"]) == 0
    assert "1 module(s) document every key they return" in capsys.readouterr().out


def test_main_check_fails_and_names_the_module(tree, returns, capsys):
    write_module(tree, "demo", module(
        "widget:\n  description: The widget.\n  returned: success\n  type: dict\n",
        "module.exit_json(changed=True, widget={}, extra=1)"))
    assert returns.main(["--check"]) == 1
    assert "demo returns extra" in capsys.readouterr().err
