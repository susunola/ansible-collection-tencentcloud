"""Unit tests for the tcb_static_store write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TCB client whose
create/destroy operations mutate a static-store list so the post-write
``wait`` reconciliation converges immediately.

Scenario matrix:

* absent on a missing store (idempotent no-op, offline store treated absent)
* absent with a live store (check-mode dry run, real destroy with an
  explicit or discovered CDN domain, missing-domain guard)
* creation when missing (check mode, enable_union, external_storage payload)
* no-op when the store is already online
* an existing non-online store (check-mode report and wait-to-online)
* unsuccessful create/destroy results and the multiple-active guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcb_static_store as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENV_ID = "env-abcdefgh"


def _store(**overrides):
    item = {
        "EnvId": ENV_ID,
        "Status": "online",
        "CdnDomain": "static-%s.example.com" % ENV_ID,
        "EnableUnion": True,
    }
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"env_id": ENV_ID}
    params.update(overrides)
    return module_args(**params)


class FakeTcbClient(object):
    """In-memory CloudBase (tcb) static-store client."""

    def __init__(self, entries=None, create_result="success", destroy_result="success"):
        self.entries = [copy.deepcopy(t) for t in (entries or [])]
        self.calls = []
        # env_id -> statuses handed out one per DescribeStaticStore call so a
        # non-online store can converge to "online" on the waiter's first poll.
        self.status_seq = {}
        self.create_result = create_result
        self.destroy_result = destroy_result

    def _by_env(self, env_id):
        return [e for e in self.entries if e.get("EnvId") == env_id]

    def DescribeStaticStore(self, request):
        self.calls.append(("DescribeStaticStore", request))
        seq = self.status_seq.get(getattr(request, "EnvId", None))
        items = []
        for entry in self._by_env(request.EnvId):
            data = copy.deepcopy(entry)
            if seq:
                data["Status"] = seq.pop(0)
            items.append(FakeResource(data))
        return SimpleNamespace(Data=items)

    def CreateStaticStore(self, request):
        self.calls.append(("CreateStaticStore", request))
        self.entries.append(
            {
                "EnvId": request.EnvId,
                "EnableUnion": bool(getattr(request, "EnableUnion", True)),
                "Status": "online",
                "CdnDomain": "static-%s.example.com" % request.EnvId,
            }
        )
        return SimpleNamespace(Result=self.create_result)

    def DestroyStaticStore(self, request):
        self.calls.append(("DestroyStaticStore", request))
        self.entries = [e for e in self.entries if e.get("EnvId") != request.EnvId]
        return SimpleNamespace(Result=self.destroy_result)


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TcbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


def _request(fake, op_name):
    for op, request in fake.calls:
        if op == op_name:
            return request
    return None


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_store_is_idempotent(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["static_store"] is None
    assert _ops(fake) == ["DescribeStaticStore"]


def test_absent_offline_store_is_absent(monkeypatch):
    fake = FakeTcbClient(entries=[_store(Status="offline")])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["static_store"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcbClient(entries=[_store()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["static_store"]["Status"] == "online"
    assert len(fake.entries) == 1
    assert "DestroyStaticStore" not in _ops(fake)


def test_absent_destroys_with_explicit_cdn_domain(monkeypatch):
    fake = FakeTcbClient(entries=[_store()])
    _make_module(monkeypatch, fake)
    _base(state="absent", cdn_domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.entries == []
    assert "DestroyStaticStore" in _ops(fake)
    destroy_request = _request(fake, "DestroyStaticStore")
    assert destroy_request.EnvId == ENV_ID
    assert destroy_request.CdnDomain == "cdn.example.com"


def test_absent_destroys_with_discovered_cdn_domain(monkeypatch):
    fake = FakeTcbClient(entries=[_store(CdnDomain="auto.example.com")])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.entries == []
    destroy_request = _request(fake, "DestroyStaticStore")
    assert destroy_request.CdnDomain == "auto.example.com"


def test_absent_missing_cdn_domain_fails(monkeypatch):
    store = _store()
    store.pop("CdnDomain")
    fake = FakeTcbClient(entries=[store])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "cdn_domain was not returned by CloudBase" in payload["msg"]
    assert payload["static_store"]["EnvId"] == ENV_ID


def test_absent_destroy_rejected_fails(monkeypatch):
    fake = FakeTcbClient(entries=[_store()], destroy_result="fail")
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "CloudBase rejected static store destruction"


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_missing_store_creates(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["static_store"]["Status"] == "online"
    assert result["static_store"]["EnvId"] == ENV_ID
    assert len(fake.entries) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeStaticStore"
    assert "CreateStaticStore" in ops


def test_create_request_carries_default_enable_union(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    run(mod.run_module)
    create_request = _request(fake, "CreateStaticStore")
    assert create_request.EnvId == ENV_ID
    assert create_request.EnableUnion is True


def test_create_with_enable_union_false(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _base(state="present", enable_union=False)
    run(mod.run_module)
    create_request = _request(fake, "CreateStaticStore")
    assert create_request.EnableUnion is False


def test_create_with_external_storage(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    payload = {"Type": "bucket", "Prefix": "assets", "RetainDays": 7}
    _base(state="present", external_storage=payload)
    run(mod.run_module)
    create_request = _request(fake, "CreateStaticStore")
    external = getattr(create_request, "ExternalStorage", None)
    assert external is not None
    assert dict(external.__dict__) == payload


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["static_store"] == {"EnvId": ENV_ID, "Status": "online"}
    assert fake.entries == []
    assert "CreateStaticStore" not in _ops(fake)


def test_present_ignores_offline_store_and_creates(monkeypatch):
    fake = FakeTcbClient(entries=[_store(Status="offline")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["static_store"]["Status"] == "online"
    assert len(fake.entries) == 2


# ---------------------------------------------------------------------------
# existing-store flows
# ---------------------------------------------------------------------------


def test_present_online_store_is_noop(monkeypatch):
    fake = FakeTcbClient(entries=[_store()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["static_store"]["CdnDomain"] == "static-%s.example.com" % ENV_ID
    assert "CreateStaticStore" not in _ops(fake)


def test_present_creating_store_check_mode_is_noop(monkeypatch):
    fake = FakeTcbClient(entries=[_store(Status="creating")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["static_store"]["Status"] == "creating"


def test_present_creating_store_waits_to_online(monkeypatch):
    fake = FakeTcbClient(entries=[_store(Status="creating")])
    fake.status_seq[ENV_ID] = ["creating", "online"]
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["static_store"]["Status"] == "online"
    assert "CreateStaticStore" not in _ops(fake)


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_active_stores_fail(monkeypatch):
    fake = FakeTcbClient(entries=[_store(), _store(CdnDomain="dupe.example.com")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple active CloudBase static stores" in exc.value.args[0]["msg"]


def test_create_rejected_fails(monkeypatch):
    fake = FakeTcbClient(create_result="fail")
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "CloudBase rejected static store creation"


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeStaticStore(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tcb_static_store.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    def from_json_string(self, raw):
        self.raw = raw


class LegacyModels(object):
    DescribeStaticStoreRequest = LegacyValue
    CreateStaticStoreRequest = LegacyValue
    DestroyStaticStoreRequest = LegacyValue
    ExternalStorage = LegacyValue


def test_static_store_requests_are_environment_scoped():
    assert mod.describe_request(LegacyModels, "env-1").EnvId == "env-1"
    create = mod.create_request(LegacyModels, {"env_id": "env-1", "enable_union": True, "external_storage": {"Type": "cos"}})
    assert create.EnableUnion is True
    assert '"Type": "cos"' in create.ExternalStorage.raw
    delete = mod.delete_request(LegacyModels, "env-1", "cdn.example.com")
    assert delete.CdnDomain == "cdn.example.com"
