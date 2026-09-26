"""Unit tests for the cos_bucket_intelligent_tiering_info module.

Like its certificate sibling this module was referenced by no test file, so
nothing in the tree said whether it worked. ``run_module`` resolves the bucket
name, reads the default intelligent-tiering rule and returns it as both a list
and a single value; these tests drive that end to end with the reader
monkeypatched.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import (
    cos_bucket_intelligent_tiering_info as mod,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
RULE = {"Status": "Enabled", "Days": 30, "Transition": {"Days": 30}}


class FakeCosError(Exception):
    """Stand-in for a ``qcloud_cos`` service error."""


@pytest.fixture
def cos_client(monkeypatch):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: "client")


def _read(monkeypatch, value):
    calls = []

    def fake(client, bucket):
        calls.append((client, bucket))
        return value

    monkeypatch.setattr(mod, "get_rule", fake)
    return calls


def test_run_module_returns_the_rule_twice(cos_client, monkeypatch):
    calls = _read(monkeypatch, RULE)
    module_args(name="archive", appid=APPID)

    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["intelligent_tiering_rules"] == [RULE]
    assert result["intelligent_tiering"] == RULE
    assert calls == [("client", "archive-%s" % APPID)]


def test_run_module_returns_empty_keys_without_a_rule(cos_client, monkeypatch):
    _read(monkeypatch, None)
    module_args(name="archive", appid=APPID)

    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["intelligent_tiering_rules"] == []
    assert result["intelligent_tiering"] is None


def test_run_module_accepts_an_already_suffixed_bucket(cos_client, monkeypatch):
    calls = _read(monkeypatch, RULE)
    module_args(name="archive-%s" % APPID, appid=APPID)

    run(mod.run_module)

    assert calls[0][1] == "archive-%s" % APPID


def test_run_module_maps_a_cos_error_to_fail_json(cos_client, monkeypatch):
    def boom(client, bucket):
        raise FakeCosError("no such bucket")

    monkeypatch.setattr(mod, "get_rule", boom)
    module_args(name="archive", appid=APPID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert "Tencent Cloud COS request failed" in failure.value.args[0]["msg"]
    assert "no such bucket" in failure.value.args[0]["error"]
