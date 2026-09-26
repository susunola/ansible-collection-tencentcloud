"""Unit tests for the cos_*_info modules nothing referenced.

``cos_bucket_inventory_info``, ``cos_bucket_object_lock_info``,
``cos_bucket_origin_info``, ``cos_bucket_referer_info``,
``cos_bucket_replication_info`` and ``cos_bucket_response_control_info`` were
named by no test file and no
integration target: nothing anywhere executed them, so nothing could tell
whether they worked. They share one shape -- resolve the bucket name, read one
value through ``module_utils/cos_bucket_read`` and return it as both a list and
a single value -- so they are covered here by one parametrised suite rather
than by six copies of the same file.

``scripts/check_quality_gates.py`` fails when a hand-written module is
referenced by nothing under ``tests/unit/``, which is how these were found.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
VALUE = {"Status": "Enabled"}

#: module name, the return keys it documents, and a value of the shape the
#: reader yields.
CASES = (
    ("cos_bucket_inventory_info", "inventories", "inventory",
     {"inventory_id": "inv-1"}),
    ("cos_bucket_object_lock_info", "object_locks", "object_lock", {}),
    ("cos_bucket_origin_info", "origins", "origin", {}),
    ("cos_bucket_referer_info", "referers", "referer", {}),
    ("cos_bucket_replication_info", "replications", "replication", {}),
    ("cos_bucket_response_control_info", "response_controls", "response_control", {}),
)


class FakeCosError(Exception):
    """Stand-in for a ``qcloud_cos`` service error."""


def _module(name):
    return importlib.import_module(
        "ansible_collections.susunola.tencentcloud.plugins.modules.%s" % name)


@pytest.fixture
def cos_client(monkeypatch):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: "client")


def _patch_readers(monkeypatch, module, calls, value):
    """Replace every reader the module imported from ``cos_bucket_read``.

    Some of these modules call more than one reader (``cos_bucket_domain_info``
    asks for the domains and for their TXT verification records), so patching
    by name one at a time would leave the other reaching a fake client.
    """
    patched = 0
    for name, attribute in list(vars(module).items()):
        if not callable(attribute):
            continue
        if not getattr(attribute, "__module__", "").endswith("cos_bucket_read"):
            continue

        def fake(*args, _name=name, **kwargs):
            calls.append((_name, args))
            return value

        monkeypatch.setattr(module, name, fake)
        patched += 1
    assert patched, "no reader was patched, so the test would prove nothing"


@pytest.mark.parametrize("name,plural,singular,extra", CASES)
def test_run_module_returns_the_value_twice(cos_client, monkeypatch, name,
                                            plural, singular, extra):
    module = _module(name)
    calls = []
    _patch_readers(monkeypatch, module, calls, VALUE)
    module_args(name="archive", appid=APPID, **extra)

    result = run(module.run_module)

    assert result["changed"] is False
    assert result[plural] == [VALUE]
    assert result[singular] == VALUE
    assert all(args[1] == "archive-%s" % APPID for _reader, args in calls)


@pytest.mark.parametrize("name,plural,singular,extra", CASES)
def test_run_module_returns_empty_keys_without_a_value(cos_client, monkeypatch,
                                                       name, plural, singular,
                                                       extra):
    module = _module(name)
    _patch_readers(monkeypatch, module, [], None)
    module_args(name="archive", appid=APPID, **extra)

    result = run(module.run_module)

    assert result["changed"] is False
    assert result[plural] == []
    assert result[singular] is None


@pytest.mark.parametrize("name,plural,singular,extra", CASES)
def test_run_module_maps_a_cos_error_to_fail_json(cos_client, monkeypatch, name,
                                                  plural, singular, extra):
    module = _module(name)

    def boom(*args, **kwargs):
        raise FakeCosError("no such bucket")

    for attribute_name, attribute in list(vars(module).items()):
        if callable(attribute) and getattr(attribute, "__module__", "").endswith(
                "cos_bucket_read"):
            monkeypatch.setattr(module, attribute_name, boom)
    module_args(name="archive", appid=APPID, **extra)

    with pytest.raises(AnsibleFailJson) as failure:
        run(module.run_module)

    assert "Tencent Cloud COS request failed" in failure.value.args[0]["msg"]
    assert "no such bucket" in failure.value.args[0]["error"]
