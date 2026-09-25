# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Request-builder and input-guard tests for the api_gateway_api_key module.

The module's behaviour flows -- create, rotate, delete, check mode, the
duplicate-name guard and the SDK error envelope -- are covered by
``test_api_gateway_api_key_main.py`` with a store-backed fake client. What
that file cannot see is the request the module puts on the wire, and one of
these builders carries a secret: ``build_create`` copies the caller's
``access_key_secret`` into the request in manual mode and must not do so in
auto mode, where the API generates the key. A regression there would send a
credential the caller never supplied, or silently ignore the one they did.

That is the scope of this file: what each builder puts in the request, and
the argument gate that runs before any of them.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_api_key as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)


def _params(**overrides):
    """The module's parameters with the argument-spec defaults applied."""
    params = {
        "access_key_id": None,
        "access_key_secret": None,
        "key_type": "auto",
        "name": None,
        "state": "present",
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------

def test_build_get_carries_the_key_id():
    request = mod.build_get(FakeModels(), "key-xxxx")
    assert request.AccessKeyId == "key-xxxx"


def test_build_list_pages_from_the_start():
    request = mod.build_list(FakeModels(), None)
    assert request.Offset == 0
    assert request.Limit == 100


def test_build_list_filters_by_secret_name():
    request = mod.build_list(FakeModels(), "name-xxxx")
    assert [item.Name for item in request.Filters] == ["SecretName"]
    assert [item.Values for item in request.Filters] == [["name-xxxx"]]


def test_build_list_omits_the_filter_when_no_name_is_given():
    """The module looks a key up by name through this filter; sending an
    empty filter list would ask the API for a name that matches everything."""
    request = mod.build_list(FakeModels(), "")
    assert not hasattr(request, "Filters")


def test_build_create_in_auto_mode_lets_the_api_generate_the_key():
    request = mod.build_create(FakeModels(), _params(name="production-client", key_type="auto"))
    assert request.SecretName == "production-client"
    assert request.AccessKeyType == "auto"
    # The caller supplied no credential material and none is invented.
    assert not hasattr(request, "AccessKeyId")
    assert not hasattr(request, "AccessKeySecret")


def test_build_create_in_manual_mode_sends_the_supplied_credential():
    request = mod.build_create(FakeModels(), _params(
        name="production-client", key_type="manual",
        access_key_id="AKIDxxxxxxxx", access_key_secret="secret-xxxxxxxx"))
    assert request.AccessKeyType == "manual"
    assert request.AccessKeyId == "AKIDxxxxxxxx"
    assert request.AccessKeySecret == "secret-xxxxxxxx"


def test_build_update_carries_the_new_secret():
    request = mod.build_update(FakeModels(), "key-xxxx", "secret-xxxx")
    assert request.AccessKeyId == "key-xxxx"
    assert request.AccessKeySecret == "secret-xxxx"


def test_build_delete_carries_the_key_id():
    request = mod.build_delete(FakeModels(), "key-xxxx")
    assert request.AccessKeyId == "key-xxxx"


# ---------------------------------------------------------------------------
# input guards
# ---------------------------------------------------------------------------

def test_a_call_with_neither_name_nor_key_id_is_rejected(monkeypatch):
    """Deleting without an identifier would leave the module with nothing to
    look up, so the argument gate rejects it before any request is built."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["failed"] is True
