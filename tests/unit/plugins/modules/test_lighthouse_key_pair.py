"""Unit tests for the lighthouse_key_pair write module (helpers + run_module).

Covers the import / delete / associate / disassociate and force-replace
flows of ``plugins/modules/lighthouse_key_pair.py`` with an in-memory fake
Lighthouse client whose write operations mutate the key-pair store, so the
module's post-write re-describes converge immediately.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import lighthouse_key_pair as lkp
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockPublicKeyMaterial"

KEY = {
    "KeyId": "lhkey-8b0a1c2d",
    "KeyName": "production-automation",
    "PublicKey": PUBLIC_KEY,
    "AssociatedInstanceIds": [],
}

WRITE_OPS = (
    "ImportKeyPair",
    "DeleteKeyPairs",
    "AssociateInstancesKeyPairs",
    "DisassociateInstancesKeyPairs",
)


def _key(**overrides):
    """Return a key fixture isolated from the shared KEY constant."""
    key = copy.deepcopy(KEY)
    key.update(overrides)
    return key


def _params(**overrides):
    params = {
        "key_id": None,
        "name": "production-automation",
        "public_key": PUBLIC_KEY,
        "instance_ids": [],
        "association_type": "ONLINE",
        "username": "root",
    }
    params.update(overrides)
    return params


class FakeLighthouseClient(object):
    """In-memory Lighthouse key-pair client that mutates a small store."""

    def __init__(self, keys=None):
        self.keys = [copy.deepcopy(key) for key in (keys or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, key_id):
        return next(key for key in self.keys if key["KeyId"] == key_id)

    def DescribeKeyPairs(self, request):
        self._record("DescribeKeyPairs", request)
        keys = self.keys
        if getattr(request, "KeyIds", None):
            wanted = set(request.KeyIds)
            keys = [key for key in keys if key["KeyId"] in wanted]
        offset = request.Offset or 0
        limit = request.Limit or len(keys)
        page = keys[offset:offset + limit]
        return SimpleNamespace(
            KeyPairSet=[FakeResource(dict(key)) for key in page],
            TotalCount=len(keys),
        )

    def ImportKeyPair(self, request):
        self._record("ImportKeyPair", request)
        key_id = "lhkey-new-%d" % (len(self.keys) + 1)
        self.keys.append(
            {
                "KeyId": key_id,
                "KeyName": request.KeyName,
                "PublicKey": request.PublicKey,
                "AssociatedInstanceIds": [],
            }
        )
        return SimpleNamespace(KeyId=key_id)

    def DeleteKeyPairs(self, request):
        self._record("DeleteKeyPairs", request)
        removed = set(request.KeyIds)
        self.keys = [key for key in self.keys if key["KeyId"] not in removed]
        return SimpleNamespace()

    def AssociateInstancesKeyPairs(self, request):
        self._record("AssociateInstancesKeyPairs", request)
        for key_id in request.KeyIds:
            key = self._by_id(key_id)
            key["AssociatedInstanceIds"] = sorted(
                set(key.get("AssociatedInstanceIds") or []) | set(request.InstanceIds)
            )
        return SimpleNamespace()

    def DisassociateInstancesKeyPairs(self, request):
        self._record("DisassociateInstancesKeyPairs", request)
        for key_id in request.KeyIds:
            key = self._by_id(key_id)
            key["AssociatedInstanceIds"] = sorted(
                set(key.get("AssociatedInstanceIds") or []) - set(request.InstanceIds)
            )
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeLighthouseClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        lkp,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(LighthouseClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_describe_request_filters_by_key_id():
    request = lkp.describe_request(FakeModels(), _params(key_id="lhkey-1"), offset=0)
    assert request.KeyIds == ["lhkey-1"]
    assert request.Offset == 0
    assert request.Limit == 100


def test_describe_request_without_key_id_has_no_key_ids():
    request = lkp.describe_request(FakeModels(), _params(key_id=None), offset=20)
    assert request.Offset == 20
    assert request.Limit == 100
    assert not hasattr(request, "KeyIds") or request.KeyIds is None


def test_import_request_sets_name_and_strips_public_key():
    request = lkp.import_request(FakeModels(), _params(public_key="  %s  " % PUBLIC_KEY))
    assert request.KeyName == "production-automation"
    assert request.PublicKey == PUBLIC_KEY


def test_delete_request_sets_key_ids():
    request = lkp.delete_request(FakeModels(), "lhkey-8b0a1c2d")
    assert request.KeyIds == ["lhkey-8b0a1c2d"]


def test_associate_request_sets_fields_and_username_when_online():
    params = _params(instance_ids=["lhins-2", "lhins-1"])
    request = lkp.associate_request(FakeModels(), params, "lhkey-1", {"lhins-2", "lhins-1"})
    assert request.KeyIds == ["lhkey-1"]
    assert request.InstanceIds == ["lhins-1", "lhins-2"]
    assert request.AssociateType == "ONLINE"
    assert request.Username == "root"


def test_associate_request_omits_username_when_offline():
    params = _params(association_type="OFFLINE", instance_ids=["lhins-1"])
    request = lkp.associate_request(FakeModels(), params, "lhkey-1", {"lhins-1"})
    assert request.AssociateType == "OFFLINE"
    assert not hasattr(request, "Username") or request.Username is None


def test_disassociate_request_sets_type_and_username_when_online():
    params = _params(instance_ids=["lhins-1"])
    request = lkp.disassociate_request(FakeModels(), params, "lhkey-1", {"lhins-1"})
    assert request.KeyIds == ["lhkey-1"]
    assert request.InstanceIds == ["lhins-1"]
    assert request.DisassociateType == "ONLINE"
    assert request.Username == "root"


def test_instances_reads_associated_instance_ids_sorted():
    value = {"AssociatedInstanceIds": ["lhins-2", "lhins-1"]}
    assert lkp._instances(value) == ["lhins-1", "lhins-2"]


def test_instances_reads_associated_instance_set():
    value = {
        "AssociatedInstanceIds": [],
        "AssociatedInstanceSet": [
            {"InstanceId": "lhins-2"},
            {"InstanceId": "lhins-1"},
            {"InstanceId": None},
        ],
    }
    assert lkp._instances(value) == ["lhins-1", "lhins-2"]


def test_instances_empty_when_unbound():
    assert lkp._instances({}) == []
    assert lkp._instances({"AssociatedInstanceIds": []}) == []


def test_comparable_normalizes_key():
    value = {
        "KeyName": "production-automation",
        "PublicKey": "  %s  " % PUBLIC_KEY,
        "AssociatedInstanceIds": ["lhins-2", "lhins-1"],
    }
    assert lkp.comparable(value) == {
        "KeyName": "production-automation",
        "PublicKey": PUBLIC_KEY,
        "InstanceIds": ["lhins-1", "lhins-2"],
    }


def test_desired_strips_public_key_and_sorts_instance_ids():
    assert lkp.desired(_params(instance_ids=["lhins-2", "lhins-1"])) == {
        "KeyName": "production-automation",
        "PublicKey": PUBLIC_KEY,
        "InstanceIds": ["lhins-1", "lhins-2"],
    }


def test_find_returns_single_key_by_id():
    module = FakeModule()
    client = FakeLighthouseClient(keys=[_key(), _key(KeyId="lhkey-2", KeyName="other")])
    found = lkp.find(module, client, FakeModels(), _params(key_id="lhkey-8b0a1c2d"))
    assert found["KeyId"] == "lhkey-8b0a1c2d"
    assert found["KeyName"] == "production-automation"


def test_find_returns_single_key_by_name():
    module = FakeModule()
    client = FakeLighthouseClient(keys=[_key()])
    found = lkp.find(module, client, FakeModels(), _params(key_id=None))
    assert found["KeyId"] == "lhkey-8b0a1c2d"


def test_find_missing_returns_none():
    module = FakeModule()
    client = FakeLighthouseClient()
    assert lkp.find(module, client, FakeModels(), _params(key_id="lhkey-9")) is None


def test_find_multiple_matches_fails():
    module = FakeModule()
    client = FakeLighthouseClient(keys=[_key(), _key(KeyId="lhkey-2")])
    with pytest.raises(AnsibleFailJson) as exc:
        lkp.find(module, client, FakeModels(), _params(key_id=None))
    assert "Multiple Lighthouse key pairs matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_one_hundred():
    module = FakeModule()
    keys = [_key(KeyId="lhkey-%03d" % index, KeyName="kp-%03d" % index) for index in range(101)]
    client = FakeLighthouseClient(keys=keys)
    found = lkp.find(module, client, FakeModels(), _params(key_id=None, name="kp-100"))
    assert found["KeyId"] == "lhkey-100"
    offsets = [request.Offset for name, request in client.calls if name == "DescribeKeyPairs"]
    assert offsets == [0, 100]


def test_remove_disassociates_bound_then_deletes():
    module = FakeModule()
    client = FakeLighthouseClient(keys=[_key(AssociatedInstanceIds=["lhins-1", "lhins-2"])])
    current = client.keys[0]
    lkp.remove(module, client, FakeModels(), _params(), current)
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DisassociateInstancesKeyPairs", "DeleteKeyPairs"]
    assert client.keys == []


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_key_id_or_name_required(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(lkp.run_module)
    assert "required" in exc.value.args[0]["msg"]


def test_present_requires_name_and_public_key(client):
    module_args(state="present", key_id="lhkey-8b0a1c2d", name="production-automation")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lkp.run_module)
    assert "name and public_key are required when state=present" in exc.value.args[0]["msg"]


def test_absent_missing_key_is_unchanged(client):
    module_args(state="absent", name="does-not-exist")
    result = run(lkp.run_module)
    assert result["changed"] is False
    assert result["key_pair"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_unbound_key(client):
    client.keys = [_key()]
    module_args(state="absent", key_id="lhkey-8b0a1c2d")
    result = run(lkp.run_module)
    assert result["changed"] is True
    assert any(name == "DeleteKeyPairs" for name, request in client.calls)
    assert client.keys == []


def test_absent_associated_requires_force_delete(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(state="absent", key_id="lhkey-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lkp.run_module)
    payload = exc.value.args[0]
    assert "set force_delete=true" in payload["msg"]
    assert payload["instance_ids"] == ["lhins-1"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_force_delete_disassociates_then_deletes(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(state="absent", key_id="lhkey-8b0a1c2d", force_delete=True)
    result = run(lkp.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DisassociateInstancesKeyPairs", "DeleteKeyPairs"]
    assert client.keys == []


def test_check_mode_absent_makes_no_writes(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(state="absent", key_id="lhkey-8b0a1c2d", force_delete=True, _ansible_check_mode=True)
    result = run(lkp.run_module)
    assert result["changed"] is True
    assert result["key_pair"]["KeyId"] == "lhkey-8b0a1c2d"
    assert result["diff"]["before"]["KeyName"] == "production-automation"
    assert result["diff"]["after"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_imports_new_key(client):
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY)
    result = run(lkp.run_module)
    assert result["changed"] is True
    assert any(name == "ImportKeyPair" for name, request in client.calls)
    assert len(client.keys) == 1
    assert client.keys[0]["KeyId"] == "lhkey-new-1"
    assert result["key_pair"]["KeyId"] == "lhkey-new-1"
    assert result["key_pair"]["KeyName"] == "production-automation"


def test_present_imports_and_associates(client):
    module_args(
        state="present",
        name="production-automation",
        public_key=PUBLIC_KEY,
        instance_ids=["lhins-2", "lhins-1"],
        username="root",
    )
    result = run(lkp.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["ImportKeyPair", "AssociateInstancesKeyPairs"]
    associate = next(request for name, request in client.calls if name == "AssociateInstancesKeyPairs")
    assert associate.InstanceIds == ["lhins-1", "lhins-2"]
    assert associate.Username == "root"
    assert result["key_pair"]["AssociatedInstanceIds"] == ["lhins-1", "lhins-2"]


def test_check_mode_present_import_makes_no_writes(client):
    module_args(
        state="present",
        name="production-automation",
        public_key=PUBLIC_KEY,
        instance_ids=["lhins-1"],
        _ansible_check_mode=True,
    )
    result = run(lkp.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["KeyName"] == "production-automation"
    assert result["key_pair"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_matching_key_is_unchanged(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY, instance_ids=["lhins-1"])
    result = run(lkp.run_module)
    assert result["changed"] is False
    assert result["key_pair"]["KeyId"] == "lhkey-8b0a1c2d"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_public_key_drift_requires_force_replace(client):
    client.keys = [_key()]
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY + "-rotated")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lkp.run_module)
    assert "immutable" in exc.value.args[0]["msg"]
    assert "force_replace=true" in exc.value.args[0]["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_force_replace_reimports_with_associations(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(
        state="present",
        key_id="lhkey-8b0a1c2d",
        name="rotated-key",
        public_key=PUBLIC_KEY + "-rotated",
        instance_ids=["lhins-2"],
        force_replace=True,
        username="root",
    )
    result = run(lkp.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == [
        "DisassociateInstancesKeyPairs",
        "DeleteKeyPairs",
        "ImportKeyPair",
        "AssociateInstancesKeyPairs",
    ]
    assert len(client.keys) == 1
    assert client.keys[0]["KeyName"] == "rotated-key"
    assert client.keys[0]["AssociatedInstanceIds"] == ["lhins-2"]
    assert result["key_pair"]["KeyName"] == "rotated-key"
    assert result["key_pair"]["AssociatedInstanceIds"] == ["lhins-2"]


def test_check_mode_present_replace_makes_no_writes(client):
    client.keys = [_key()]
    module_args(
        state="present",
        key_id="lhkey-8b0a1c2d",
        name="rotated-key",
        public_key=PUBLIC_KEY,
        force_replace=True,
        _ansible_check_mode=True,
    )
    result = run(lkp.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["KeyName"] == "production-automation"
    assert result["diff"]["after"]["KeyName"] == "rotated-key"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_adds_association(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY, instance_ids=["lhins-1", "lhins-2"])
    result = run(lkp.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["AssociateInstancesKeyPairs"]
    assert not any(name == "DisassociateInstancesKeyPairs" for name, request in client.calls)
    assert client.keys[0]["AssociatedInstanceIds"] == ["lhins-1", "lhins-2"]


def test_present_removes_association(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1", "lhins-2"])]
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY, instance_ids=["lhins-1"])
    result = run(lkp.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DisassociateInstancesKeyPairs"]
    assert not any(name == "AssociateInstancesKeyPairs" for name, request in client.calls)
    assert client.keys[0]["AssociatedInstanceIds"] == ["lhins-1"]


def test_present_switches_association(client):
    client.keys = [_key(AssociatedInstanceIds=["lhins-1"])]
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY, instance_ids=["lhins-2"])
    result = run(lkp.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DisassociateInstancesKeyPairs", "AssociateInstancesKeyPairs"]
    assert client.keys[0]["AssociatedInstanceIds"] == ["lhins-2"]


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("lighthouse api exploded")

    client.DescribeKeyPairs = boom
    module_args(state="present", name="production-automation", public_key=PUBLIC_KEY)
    with pytest.raises(AnsibleFailJson) as exc:
        run(lkp.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "lighthouse api exploded" in payload["error"]
