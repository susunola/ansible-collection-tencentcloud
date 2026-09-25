# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/check_plugin_options.py.

The rule is one-directional -- every documented option must be read -- and the
interesting part is what it refuses to judge: the options ansible-core's own
mixins read on the plugin's behalf. Both are pinned here, along with the real
defect the check was written for (``include_sgless`` was documented for months
and never read).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_plugin_options.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_plugin_options",
                                                  SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plugins():
    return _load_script()


@pytest.fixture
def tree(plugins, tmp_path, monkeypatch):
    """Point the script at a throwaway collection layout."""
    for directory in ("inventory", "lookup", "doc_fragments"):
        (tmp_path / "plugins" / directory).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(plugins, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(plugins, "DOC_FRAGMENTS_DIR",
                        tmp_path / "plugins" / "doc_fragments")
    return tmp_path


def _plugin_source(options, body="", fragments=(), name="tencentcloud_demo"):
    lines = ["DOCUMENTATION = r'''", "---", "name: %s" % name, "options:"]
    for option in options:
        lines += ["  %s:" % option, "    description: x", "    type: str"]
    if fragments:
        lines.append("extends_documentation_fragment:")
        for fragment in fragments:
            lines.append("  - %s" % fragment)
    lines += ["'''", "", body, ""]
    return "\n".join(lines)


def _write(tree, source, directory="inventory", name="tencentcloud_demo.py"):
    path = tree / "plugins" / directory / name
    path.write_text(source, encoding="utf-8")
    return path


def test_a_documented_option_that_is_read_passes(plugins, tree):
    _write(tree, _plugin_source(["regions"],
                                body='regions = self.get_option("regions")'))
    assert plugins.findings() == []


def test_a_documented_option_that_is_never_read_is_reported(plugins, tree):
    """The real defect: ``include_sgless`` was documented and never read."""
    _write(tree, _plugin_source(["regions", "include_sgless"],
                                body='regions = self.get_option("regions")'))
    problems = plugins.findings()
    assert len(problems) == 1
    assert "include_sgless" in problems[0]
    assert "no get_option call reads" in problems[0]


def test_an_option_the_plugin_does_not_document_is_not_a_finding(plugins, tree):
    """This rule reads one direction; an undocumented option is another."""
    _write(tree, _plugin_source(["regions"],
                                body='self.get_option("regions")\n'
                                     'self.get_option("undocumented")'))
    assert plugins.findings() == []


def test_a_collection_fragment_holds_the_plugin_to_its_options(plugins, tree):
    fragment = ("DOCUMENTATION = r'''\n---\noptions:\n  secret_id:\n"
                "    description: x\n    type: str\n'''\n")
    _write(tree, fragment, directory="doc_fragments", name="credentials.py")
    _write(tree, _plugin_source(
        ["regions"], fragments=["susunola.tencentcloud.credentials"],
        body='self.get_option("regions")'))
    problems = plugins.findings()
    assert len(problems) == 1
    assert "secret_id" in problems[0]


def test_a_builtin_fragment_is_left_to_ansible_core(plugins, tree):
    """``constructed``'s options are read by Constructable, not by the plugin."""
    _write(tree, _plugin_source(["regions"], fragments=["constructed"],
                                body='self.get_option("regions")'))
    assert plugins.findings() == []


def test_an_unknown_fragment_is_reported(plugins, tree):
    _write(tree, _plugin_source(["regions"], fragments=["nosuchfragment"],
                                body='self.get_option("regions")'))
    problems = plugins.findings()
    assert len(problems) == 1
    assert "nosuchfragment" in problems[0]


def test_the_loader_option_and_lookup_terms_are_exempt(plugins, tree):
    _write(tree, _plugin_source(["plugin", "regions"],
                                body='self.get_option("regions")'))
    assert plugins.findings() == []
    _write(tree, _plugin_source(["_terms", "secret_id"],
                                body='self.get_option("secret_id")'),
           directory="lookup", name="demo.py")
    assert plugins.findings() == []


def test_an_option_documented_as_inert_is_exempt(plugins, tree):
    assert "with_decryption" in plugins.UNUSED_BY_DESIGN
    _write(tree, _plugin_source(["with_decryption"],
                                body='self.get_option("other")'),
           directory="lookup", name="ssm_demo.py")
    assert plugins.findings() == []


def test_a_plugin_without_documentation_is_reported(plugins, tree):
    _write(tree, "x = 1\n")
    problems = plugins.findings()
    assert len(problems) == 1
    assert "no readable DOCUMENTATION block" in problems[0]


def test_check_exits_non_zero_on_a_finding(plugins, tree):
    _write(tree, _plugin_source(["regions", "include_sgless"],
                                body='self.get_option("regions")'))
    out, err = io.StringIO(), io.StringIO()
    rc = plugins.main(["--check"], out=out, err=err)
    assert rc == 1
    assert "findings (1)" in out.getvalue()
    assert "must be one the plugin reads" in err.getvalue()


def test_committed_plugins_read_every_documented_option(plugins):
    """The repository must pass the check, not just the fixture."""
    assert plugins.findings() == []
