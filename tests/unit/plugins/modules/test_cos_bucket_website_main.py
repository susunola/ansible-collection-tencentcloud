"""Unit tests for the cos_bucket_website write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_website`` operations mutate a website-config store
so the reconcile (absent no-op, create, drift update, delete) converges
immediately. The module talks to ``qcloud_cos`` through
``module_utils/cos.py`` helpers, so the tests monkeypatch
``cos.require_cos_sdk`` (no-op) and ``cos.create_cos_client`` (fake)
instead of the API 3.0 ``create_client`` path used elsewhere.

Scenario matrix:

* absent on a missing configuration (idempotent no-op)
* absent on an existing configuration (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the configuration already matches
* configuration drift triggers ``put_bucket_website``
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_website as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

WEBSITE = {
    "IndexDocument": {"Suffix": "index.html"},
    "ErrorDocument": {"Key": "error.html"},
}


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status


class FakeCosClient(object):
    """In-memory COS client mutating a website-configuration store."""

    def __init__(self, website=None):
        self.website = copy.deepcopy(website)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_website(self, Bucket, **kwargs):
        self._record("get_bucket_website", Bucket)
        if self.website is None:
            raise FakeCosError("NoSuchBucket")
        return copy.deepcopy(self.website)

    def put_bucket_website(self, Bucket, WebsiteConfiguration, **kwargs):
        self._record("put_bucket_website", WebsiteConfiguration)
        self.website = copy.deepcopy(WebsiteConfiguration)

    def delete_bucket_website(self, Bucket, **kwargs):
        self._record("delete_bucket_website", Bucket)
        self.website = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _website(**overrides):
    item = copy.deepcopy(WEBSITE)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(website=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["website"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_website"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(website=_website())
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["website"] is not None
    assert fake.website is not None
    assert "delete_bucket_website" not in [c for c, unused in fake.calls]


def test_absent_deletes_configuration(monkeypatch):
    fake = FakeCosClient(website=_website())
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["website"] is None
    assert fake.website is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_website" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_configuration(monkeypatch):
    fake = FakeCosClient(website=None)
    _make_module(monkeypatch, fake)
    _config(state="present", configuration=_website())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["website"] == WEBSITE
    assert fake.website == WEBSITE
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_website"
    assert "put_bucket_website" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(website=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", configuration=_website())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["website"] == WEBSITE
    assert fake.website is None
    assert "put_bucket_website" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-configuration flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(website=_website())
    _make_module(monkeypatch, fake)
    _config(state="present", configuration=_website())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["website"] == WEBSITE
    assert "put_bucket_website" not in [c for c, unused in fake.calls]


def test_configuration_drift_triggers_update(monkeypatch):
    updated = _website(IndexDocument={"Suffix": "home.html"})
    fake = FakeCosClient(website=_website())
    _make_module(monkeypatch, fake)
    _config(state="present", configuration=updated)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["website"]["IndexDocument"] == {"Suffix": "home.html"}
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_website" in ops


def test_check_mode_drift_does_not_write(monkeypatch):
    updated = _website(IndexDocument={"Suffix": "home.html"})
    fake = FakeCosClient(website=_website())
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", configuration=updated)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.website == WEBSITE
    assert "put_bucket_website" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_website(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present", configuration=_website())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
