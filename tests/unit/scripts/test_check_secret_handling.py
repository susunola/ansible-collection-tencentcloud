# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/check_secret_handling.py.

The rule has two directions: an option that is a secret by name must carry
``no_log: True``, and no message may interpolate its value. Both are pinned
here, along with the two cases the rule deliberately lets through -- a flag
whose name mentions a secret, and an idempotency token -- because a
name-based rule that flagged those would be switched off in a week.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_secret_handling.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_secret_handling",
                                                  SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def secrets():
    return _load_script()


def _spec(module, source):
    """Return the option specs a module source declares."""
    return {name: spec for name, spec, _node in module.option_specs(source)}


def _findings(secrets, monkeypatch, source, tmp_path):
    """Run the no_log check against *source* as if it were a module."""
    module = tmp_path / "probe.py"
    module.write_text(source, encoding="utf-8")
    monkeypatch.setattr(secrets, "plugin_sources",
                        lambda: [("plugins/modules/probe.py", module)])
    return secrets.no_log_findings()


def test_option_specs_reads_a_module_argument_spec(secrets):
    source = ('def run_module():\n'
              '    argument_spec = {\n'
              '        "name": {"type": "str"},\n'
              '        "password": {"type": "str", "no_log": True},\n'
              '    }\n')
    specs = _spec(secrets, source)
    assert set(specs) == {"name", "password"}
    assert secrets._literal(specs["password"]["no_log"]) is True


def test_option_specs_follows_nested_options(secrets):
    source = ('def run_module():\n'
              '    argument_spec = {\n'
              '        "account": {\n'
              '            "type": "dict",\n'
              '            "options": {\n'
              '                "password": {"type": "str"},\n'
              '            },\n'
              '        },\n'
              '    }\n')
    assert set(_spec(secrets, source)) == {"account", "account.password"}


def test_unguarded_secret_is_reported(secrets, monkeypatch, tmp_path):
    source = ('def run_module():\n'
              '    argument_spec = {"db_password": {"type": "str"}}\n')
    findings = _findings(secrets, monkeypatch, source, tmp_path)
    assert len(findings) == 1
    assert "db_password" in findings[0]
    assert "no_log: True" in findings[0]


def test_guarded_secret_passes(secrets, monkeypatch, tmp_path):
    source = ('def run_module():\n'
              '    argument_spec = {\n'
              '        "db_password": {"type": "str", "no_log": True}\n'
              '    }\n')
    assert _findings(secrets, monkeypatch, source, tmp_path) == []


def test_nested_unguarded_secret_is_reported(secrets, monkeypatch, tmp_path):
    source = ('def run_module():\n'
              '    argument_spec = {\n'
              '        "account": {"type": "dict", "options": {\n'
              '            "secret_key": {"type": "str"},\n'
              '        }},\n'
              '    }\n')
    findings = _findings(secrets, monkeypatch, source, tmp_path)
    assert len(findings) == 1
    assert "account.secret_key" in findings[0]


def test_a_flag_that_mentions_a_secret_is_not_a_secret(secrets, monkeypatch,
                                                       tmp_path):
    """``rotate_password`` is a bool: it cannot carry a credential."""
    source = ('def run_module():\n'
              '    argument_spec = {\n'
              '        "rotate_password": {"type": "bool", "default": False},\n'
              '    }\n')
    assert _findings(secrets, monkeypatch, source, tmp_path) == []


def test_an_idempotency_token_is_not_a_secret(secrets, monkeypatch, tmp_path):
    source = ('def run_module():\n'
              '    argument_spec = {"client_token": {"type": "str"}}\n')
    assert _findings(secrets, monkeypatch, source, tmp_path) == []


def test_a_name_that_only_mentions_a_secret_is_not_one(secrets, monkeypatch,
                                                       tmp_path):
    source = ('def run_module():\n'
              '    argument_spec = {\n'
              '        "secret_name": {"type": "str"},\n'
              '        "token_ttl": {"type": "int"},\n'
              '    }\n')
    assert _findings(secrets, monkeypatch, source, tmp_path) == []


def test_interpolated_secret_is_reported(secrets, monkeypatch, tmp_path):
    source = ('def run():\n'
              '    params = {"password": "x"}\n'
              '    return "the password is %s" % params["password"]\n')
    module = tmp_path / "probe.py"
    module.write_text(source, encoding="utf-8")
    monkeypatch.setattr(secrets, "plugin_sources",
                        lambda: [("plugins/modules/probe.py", module)])
    findings = secrets.interpolation_findings()
    assert len(findings) == 1
    assert "password" in findings[0]


def test_format_and_fstring_interpolation_are_reported(secrets, monkeypatch,
                                                       tmp_path):
    source = ('def run(secret_key, params):\n'
              '    print("{}".format(secret_key))\n'
              '    return f"key={params[\'secret_key\']}"\n')
    module = tmp_path / "probe.py"
    module.write_text(source, encoding="utf-8")
    monkeypatch.setattr(secrets, "plugin_sources",
                        lambda: [("plugins/modules/probe.py", module)])
    assert len(secrets.interpolation_findings()) == 2


def test_a_message_that_only_names_the_option_is_fine(secrets, monkeypatch,
                                                      tmp_path):
    source = ('def run():\n'
              '    raise ValueError("password is required when '
              'rotate_password=true")\n')
    module = tmp_path / "probe.py"
    module.write_text(source, encoding="utf-8")
    monkeypatch.setattr(secrets, "plugin_sources",
                        lambda: [("plugins/modules/probe.py", module)])
    assert secrets.interpolation_findings() == []


def test_check_exits_non_zero_on_a_finding(secrets, monkeypatch, tmp_path):
    module = tmp_path / "probe.py"
    module.write_text('def run_module():\n'
                      '    argument_spec = {"db_password": {"type": "str"}}\n',
                      encoding="utf-8")
    monkeypatch.setattr(secrets, "plugin_sources",
                        lambda: [("plugins/modules/probe.py", module)])
    out, err = io.StringIO(), io.StringIO()
    rc = secrets.main(["--check"], out=out, err=err)
    assert rc == 1
    assert "findings (1)" in out.getvalue()
    assert "must carry no_log: True" in err.getvalue()


def test_check_passes_on_a_clean_tree(secrets, monkeypatch, tmp_path):
    module = tmp_path / "probe.py"
    module.write_text('def run_module():\n'
                      '    argument_spec = {"name": {"type": "str"}}\n',
                      encoding="utf-8")
    monkeypatch.setattr(secrets, "plugin_sources",
                        lambda: [("plugins/modules/probe.py", module)])
    out, err = io.StringIO(), io.StringIO()
    rc = secrets.main(["--check"], out=out, err=err)
    assert rc == 0
    assert "secret handling check OK" in out.getvalue()
    assert err.getvalue() == ""


def test_committed_tree_declares_no_log_for_every_secret(secrets):
    rows = secrets.secret_options()
    assert len(rows) > 50, "the census must see the collection's options"
    assert secrets.no_log_findings() == []


def test_committed_tree_interpolates_no_secret(secrets):
    assert secrets.interpolation_findings() == []
