"""Unit tests for the ccn_attachment write module (helpers + run_module).

Covers the attach / detach / update-description flows of
``plugins/modules/ccn_attachment.py`` with an in-memory fake VPC client whose
write operations mutate the attachment store, so the module's
``wait_for_attachment`` polls converge on the first attempt. The raw timeout
path of ``wait_for_attachment`` is exercised with a patched clock so no test
sleeps.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ccn_attachment as ccn_att
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ATTACHMENT = {
    "InstanceId": "vpc-8b0a1c2d",
    "InstanceRegion": "ap-guangzhou",
    "InstanceType": "VPC",
    "Description": "production",
}

WRITE_OPS = (
    "AttachCcnInstances",
    "DetachCcnInstances",
    "ModifyCcnAttachedInstancesAttribute",
)


def _attachment(**overrides):
    """Return an attachment fixture isolated from the shared constant."""
    attachment = copy.deepcopy(ATTACHMENT)
    attachment.update(overrides)
    return attachment


def _params(**overrides):
    params = {
        "state": "present",
        "ccn_id": "ccn-8b0a1c2d",
        "instance_id": "vpc-8b0a1c2d",
        "instance_region": "ap-guangzhou",
        "instance_type": "VPC",
        "description": "production",
        "route_table_id": None,
        "waiter_timeout": 120,
        "waiter_delay": 5,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with required params + the fixture description."""
    args = {
        "ccn_id": "ccn-8b0a1c2d",
        "instance_id": "vpc-8b0a1c2d",
        "instance_region": "ap-guangzhou",
        "instance_type": "VPC",
        "description": "production",
    }
    args.update(extra)
    return module_args(**args)


class FakeVpcClient(object):
    """In-memory VPC client that mutates a small CCN attachment store."""

    def __init__(self, attachments=None):
        self.attachments = [copy.deepcopy(a) for a in (attachments or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _matches(self, attachment, instance):
        return (
            attachment["InstanceId"] == instance.InstanceId
            and attachment["InstanceRegion"] == instance.InstanceRegion
            and attachment["InstanceType"] == instance.InstanceType
        )

    def DescribeCcnAttachedInstances(self, request):
        self._record("DescribeCcnAttachedInstances", request)
        offset = request.Offset or 0
        limit = request.Limit or len(self.attachments)
        page = self.attachments[offset:offset + limit]
        return SimpleNamespace(
            InstanceSet=[FakeResource(dict(a)) for a in page],
            TotalCount=len(self.attachments),
        )

    def AttachCcnInstances(self, request):
        self._record("AttachCcnInstances", request)
        instance = request.Instances[0]
        self.attachments.append(
            {
                "InstanceId": instance.InstanceId,
                "InstanceRegion": instance.InstanceRegion,
                "InstanceType": instance.InstanceType,
                "Description": instance.Description,
            }
        )
        return SimpleNamespace()

    def DetachCcnInstances(self, request):
        self._record("DetachCcnInstances", request)
        instance = request.Instances[0]
        self.attachments = [a for a in self.attachments if not self._matches(a, instance)]
        return SimpleNamespace()

    def ModifyCcnAttachedInstancesAttribute(self, request):
        self._record("ModifyCcnAttachedInstancesAttribute", request)
        instance = request.Instances[0]
        for attachment in self.attachments:
            if self._matches(attachment, instance):
                attachment["Description"] = instance.Description
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
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        ccn_att,
        "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
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


def test_build_instance_sets_fields():
    instance = ccn_att.build_instance(FakeModels(), _params())
    assert instance.InstanceId == "vpc-8b0a1c2d"
    assert instance.InstanceRegion == "ap-guangzhou"
    assert instance.InstanceType == "VPC"
    assert instance.Description == "production"
    assert not hasattr(instance, "RouteTableId") or instance.RouteTableId is None


def test_build_instance_sets_route_table_id_when_given():
    instance = ccn_att.build_instance(FakeModels(), _params(route_table_id="ccnrtb-1"))
    assert instance.RouteTableId == "ccnrtb-1"


def test_build_describe_request_sets_ccn_and_paging():
    request = ccn_att.build_describe_request(FakeModels(), "ccn-8b0a1c2d", offset=100)
    assert request.CcnId == "ccn-8b0a1c2d"
    assert request.Offset == 100
    assert request.Limit == 100


def test_build_mutation_request_uses_given_operation():
    models = FakeModels()
    request = ccn_att.build_mutation_request(models, _params(), models.AttachCcnInstancesRequest)
    assert request.CcnId == "ccn-8b0a1c2d"
    assert request.Instances[0].InstanceId == "vpc-8b0a1c2d"


def test_find_attachment_returns_matching_entry():
    module = FakeModule()
    client = FakeVpcClient(attachments=[_attachment(), _attachment(InstanceId="vpc-2")])
    found = ccn_att.find_attachment(module, client, FakeModels(), _params())
    assert found["InstanceId"] == "vpc-8b0a1c2d"
    assert found["Description"] == "production"


def test_find_attachment_ignores_other_instance_types():
    module = FakeModule()
    client = FakeVpcClient(attachments=[_attachment(InstanceType="VPNGW")])
    assert ccn_att.find_attachment(module, client, FakeModels(), _params()) is None


def test_find_attachment_missing_returns_none():
    module = FakeModule()
    client = FakeVpcClient()
    assert ccn_att.find_attachment(module, client, FakeModels(), _params()) is None


def test_find_attachment_paginates_past_one_hundred():
    module = FakeModule()
    attachments = [_attachment(InstanceId="vpc-%03d" % index) for index in range(101)]
    attachments.append(_attachment())
    client = FakeVpcClient(attachments=attachments)
    found = ccn_att.find_attachment(module, client, FakeModels(), _params())
    assert found["InstanceId"] == "vpc-8b0a1c2d"
    offsets = [request.Offset for name, request in client.calls if name == "DescribeCcnAttachedInstances"]
    assert offsets == [0, 100]


def test_wait_for_attachment_returns_when_present():
    module = FakeModule()
    client = FakeVpcClient(attachments=[_attachment()])
    current = ccn_att.wait_for_attachment(module, client, FakeModels(), _params())
    assert current["InstanceId"] == "vpc-8b0a1c2d"


def test_wait_for_attachment_absent_returns_none_when_gone():
    module = FakeModule()
    client = FakeVpcClient()
    assert ccn_att.wait_for_attachment(module, client, FakeModels(), _params(), absent=True) is None


def test_wait_for_attachment_sleeps_between_polls(monkeypatch):
    module = FakeModule()
    client = FakeVpcClient(attachments=[_attachment(Description="stale")])
    sleeps = []
    monkeypatch.setattr(ccn_att.time, "sleep", sleeps.append)
    calls = []
    real_describe = client.DescribeCcnAttachedInstances

    def stale_then_converge(request):
        calls.append(request)
        if len(calls) > 1:
            client.attachments[0]["Description"] = "production"
        return real_describe(request)

    client.DescribeCcnAttachedInstances = stale_then_converge
    current = ccn_att.wait_for_attachment(module, client, FakeModels(), _params())
    assert current["Description"] == "production"
    assert sleeps == [5]


def test_wait_for_attachment_times_out_with_patched_clock(monkeypatch):
    module = FakeModule()
    client = FakeVpcClient(attachments=[_attachment(Description="stale")])
    ticks = iter([1000.0, 2000.0])
    monkeypatch.setattr(ccn_att.time, "time", lambda: next(ticks))
    monkeypatch.setattr(ccn_att.time, "sleep", lambda *args, **kwargs: None)
    with pytest.raises(AnsibleFailJson) as exc:
        ccn_att.wait_for_attachment(module, client, FakeModels(), _params())
    assert "Timed out waiting for CCN attachment convergence" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(ccn_att.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]


def test_absent_missing_attachment_is_unchanged(client):
    _run_args(state="absent")
    result = run(ccn_att.run_module)
    assert result["changed"] is False
    assert result["attachment"] is None
    assert "is absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_attaches_network_instance(client):
    _run_args()
    result = run(ccn_att.run_module)
    assert result["changed"] is True
    assert "attached" in result["msg"]
    assert any(name == "AttachCcnInstances" for name, request in client.calls)
    assert len(client.attachments) == 1
    assert result["attachment"]["InstanceId"] == "vpc-8b0a1c2d"
    assert result["attachment"]["Description"] == "production"


def test_present_attached_is_unchanged(client):
    client.attachments = [_attachment()]
    _run_args()
    result = run(ccn_att.run_module)
    assert result["changed"] is False
    assert "up to date" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_updates_description(client):
    client.attachments = [_attachment(Description="stale")]
    _run_args(description="production")
    result = run(ccn_att.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    assert any(name == "ModifyCcnAttachedInstancesAttribute" for name, request in client.calls)
    assert client.attachments[0]["Description"] == "production"
    assert result["attachment"]["Description"] == "production"


def test_absent_detaches_network_instance(client):
    client.attachments = [_attachment()]
    _run_args(state="absent")
    result = run(ccn_att.run_module)
    assert result["changed"] is True
    assert "detached" in result["msg"]
    assert any(name == "DetachCcnInstances" for name, request in client.calls)
    assert client.attachments == []
    assert result["attachment"] is None


def test_check_mode_attach_makes_no_writes(client):
    _run_args(_ansible_check_mode=True)
    result = run(ccn_att.run_module)
    assert result["changed"] is True
    assert "Would attach" in result["msg"]
    assert result["attachment"] is None
    assert result["diff"]["after"]["InstanceId"] == "vpc-8b0a1c2d"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_update_makes_no_writes(client):
    client.attachments = [_attachment(Description="stale")]
    _run_args(description="production", _ansible_check_mode=True)
    result = run(ccn_att.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert result["attachment"]["Description"] == "stale"
    assert result["diff"]["before"]["Description"] == "stale"
    assert result["diff"]["after"]["Description"] == "production"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_detach_makes_no_writes(client):
    client.attachments = [_attachment()]
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(ccn_att.run_module)
    assert result["changed"] is True
    assert "Would detach" in result["msg"]
    assert result["attachment"]["InstanceId"] == "vpc-8b0a1c2d"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("vpc api exploded")

    client.DescribeCcnAttachedInstances = boom
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(ccn_att.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "vpc api exploded"
    assert payload["error_code"] is None
