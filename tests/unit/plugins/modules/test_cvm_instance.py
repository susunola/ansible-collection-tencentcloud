"""Unit tests for the cvm_instance write module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cvm_instance import (
    _InstanceGone,
    _reboot,
    _reset_password,
    _reset_type,
    build_describe_request,
    build_run_request,
    find_instance,
    immutable_drift,
)


class FakeFilter(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeTag(object):
    def __init__(self):
        self.Key = None
        self.Value = None


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    Tag = FakeTag
    TagSpecification = FakeRequest
    Placement = FakeRequest
    VirtualPrivateCloud = FakeRequest
    InternetAccessible = FakeRequest
    LoginSettings = FakeRequest
    DescribeInstancesRequest = FakeRequest
    RunInstancesRequest = FakeRequest
    RebootInstancesRequest = FakeRequest
    ResetInstancesPasswordRequest = FakeRequest
    ResetInstancesTypeRequest = FakeRequest


class FakeInstance(object):
    def __init__(self, instance_id, name, state="RUNNING"):
        self.InstanceId = instance_id
        self.InstanceName = name
        self.InstanceState = state

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "InstanceName": self.InstanceName,
            "InstanceState": self.InstanceState,
        }


class FakeResponse(object):
    def __init__(self, instances):
        self.InstanceSet = instances


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeInstances(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def RebootInstances(self, request):
        self.calls.append(request)

    def ResetInstancesPassword(self, request):
        self.calls.append(request)

    def ResetInstancesType(self, request):
        self.calls.append(request)


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def _params(**overrides):
    params = {
        "instance_name": None,
        "image_id": "img-1",
        "instance_type": "S5.MEDIUM2",
        "instance_charge_type": "POSTPAID_BY_HOUR",
        "vpc_id": None,
        "subnet_id": None,
        "security_group_ids": None,
        "hostname": None,
        "password": None,
        "key_ids": None,
        "internet_charge_type": None,
        "internet_max_bandwidth_out": None,
        "public_ip_assigned": None,
        "dry_run": False,
        "tags": {},
    }
    params.update(overrides)
    return params


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "ins-123", None)
    assert request.InstanceIds == ["ins-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "web-01")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["web-01"]
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_find_instance_returns_first_match():
    client = FakeClient(FakeResponse([FakeInstance("ins-1", "web-01")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "web-01")
    assert instance["InstanceId"] == "ins-1"
    assert len(client.calls) == 1


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, None, "web-01") is None


def test_find_instance_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, None, "web-01") is None


def test_find_instance_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "InvalidInstanceId.NotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_instance(module, client, FakeModels, "ins-1", None)
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_build_run_request_minimal():
    request = build_run_request(FakeModels, _params())
    assert request.ImageId == "img-1"
    assert request.InstanceType == "S5.MEDIUM2"
    assert request.InstanceChargeType == "POSTPAID_BY_HOUR"
    assert request.Placement is not None
    assert not hasattr(request, "DryRun")
    assert not hasattr(request, "InstanceName")
    assert not hasattr(request, "VirtualPrivateCloud")
    assert not hasattr(request, "InternetAccessible")
    assert not hasattr(request, "LoginSettings")
    assert not hasattr(request, "TagSpecification")


def test_build_run_request_full():
    request = build_run_request(FakeModels, _params(
        instance_name="web-01",
        hostname="web-01",
        security_group_ids=["sg-1", "sg-2"],
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        password="secret",
        internet_charge_type="TRAFFIC_POSTPAID_BY_HOUR",
        internet_max_bandwidth_out=10,
        public_ip_assigned=True,
        dry_run=True,
        tags={"env": "prod"},
    ))
    assert request.InstanceName == "web-01"
    assert request.HostName == "web-01"
    assert request.SecurityGroupIds == ["sg-1", "sg-2"]
    assert request.VirtualPrivateCloud.VpcId == "vpc-1"
    assert request.VirtualPrivateCloud.SubnetId == "subnet-1"
    assert request.LoginSettings.Password == "secret"
    assert not hasattr(request.LoginSettings, "KeyIds")
    assert request.InternetAccessible.InternetChargeType == "TRAFFIC_POSTPAID_BY_HOUR"
    assert request.InternetAccessible.InternetMaxBandwidthOut == 10
    assert request.InternetAccessible.PublicIpAssigned is True
    assert request.DryRun is True
    assert request.TagSpecification[0].ResourceType == "instance"
    tag = request.TagSpecification[0].Tags[0]
    assert tag.Key == "env"
    assert tag.Value == "prod"


def test_build_run_request_key_ids():
    request = build_run_request(FakeModels, _params(key_ids=["skey-1"]))
    assert request.LoginSettings.KeyIds == ["skey-1"]
    assert not hasattr(request.LoginSettings, "Password")


def test_immutable_drift_none():
    current = {
        "ImageId": "img-1",
        "InstanceType": "S5.MEDIUM2",
        "VirtualPrivateCloud": {"VpcId": "vpc-1", "SubnetId": "subnet-1"},
    }
    assert immutable_drift(current, image_id="img-1", vpc_id="vpc-1", subnet_id="subnet-1") == []


def test_immutable_drift_detects_changes():
    current = {
        "ImageId": "img-1",
        "InstanceType": "S5.MEDIUM2",
        "VirtualPrivateCloud": {"VpcId": "vpc-1", "SubnetId": "subnet-1"},
    }
    assert immutable_drift(current, image_id="img-2") == ["image_id"]
    assert immutable_drift(current, vpc_id="vpc-2") == ["vpc_id"]
    assert immutable_drift(current, subnet_id="subnet-2") == ["subnet_id"]


def test_immutable_drift_ignores_instance_type():
    # The instance model is resized through ResetInstancesType on a stopped
    # instance, so it must never be reported as immutable.
    current = {"ImageId": "img-1", "InstanceType": "S5.MEDIUM2"}
    assert immutable_drift(current) == []


def test_reboot_sends_instance_ids():
    client = FakeClient()
    module = FakeModule()
    _reboot(module, client, FakeModels, "ins-123")
    assert len(client.calls) == 1
    assert client.calls[0].InstanceIds == ["ins-123"]


def test_reset_password_sends_ids_and_password():
    client = FakeClient()
    module = FakeModule()
    _reset_password(module, client, FakeModels, "ins-123", "Sup3rSecret!")
    assert len(client.calls) == 1
    assert client.calls[0].InstanceIds == ["ins-123"]
    assert client.calls[0].Password == "Sup3rSecret!"


def test_reset_type_sends_ids_and_new_model():
    client = FakeClient()
    module = FakeModule()
    _reset_type(module, client, FakeModels, "ins-123", "S5.LARGE4")
    assert len(client.calls) == 1
    assert client.calls[0].InstanceIds == ["ins-123"]
    assert client.calls[0].InstanceType == "S5.LARGE4"


def test_immutable_drift_ignores_unset_params():
    current = {"ImageId": "img-1", "VirtualPrivateCloud": None}
    assert immutable_drift(current) == []


def test_instance_gone_reports_not_found_code():
    assert _InstanceGone("gone").get_code() == "InvalidInstanceId.NotFound"


# ---------------------------------------------------------------------------
# exact_count pool scaling (cvm_instance additions)
# ---------------------------------------------------------------------------

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import (  # noqa: E402
    TencentCloudModule,
)
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance  # noqa: E402
from tests.unit.plugins.modules.harness import (  # noqa: E402
    AnsibleExitJson,
    AnsibleFailJson,
    module_args,
    run,
    set_module_args,
)


class FakeScalingRequest(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeScalingModels(object):
    DescribeInstancesRequest = FakeScalingRequest
    RunInstancesRequest = FakeScalingRequest
    TerminateInstancesRequest = FakeScalingRequest
    Filter = FakeScalingRequest
    Placement = FakeScalingRequest
    TagSpecification = FakeScalingRequest
    Tag = FakeTag
    VirtualPrivateCloud = FakeScalingRequest
    InternetAccessible = FakeScalingRequest
    LoginSettings = FakeScalingRequest


class FakeScalingResponse(object):
    def __init__(self, instances, total, new_ids=None):
        self.InstanceSet = instances
        self.TotalCount = total
        if new_ids is not None:
            self.InstanceIdSet = ["ins-new-%d" % i for i in range(new_ids)]


class FakeScalingClient(object):
    """Serves offset-sliced describe pages over a mutable instance set."""

    def __init__(self, all_instances, page_size=2):
        self.all = list(all_instances)
        self.page_size = page_size
        self.describe_calls = 0
        self.run_requests = []
        self.term_requests = []

    def DescribeInstances(self, request):
        self.describe_calls += 1
        start = request.Offset or 0
        page = self.all[start:start + self.page_size]
        return FakeScalingResponse(page, len(self.all))

    def RunInstances(self, request):
        self.run_requests.append(request)
        for index in range(request.InstanceCount or 1):
            self.all.append(_scaling_resource("ins-new-%d" % index))
        return FakeScalingResponse([], 0, new_ids=request.InstanceCount or 1)

    def TerminateInstances(self, request):
        self.term_requests.append(request)
        doomed = set(request.InstanceIds)
        self.all = [item for item in self.all if item.InstanceId not in doomed]
        return FakeScalingResponse([], 0)


class FakeScalingModule(object):
    def __init__(self, client, check_mode=False):
        self._client = client
        self.check_mode = check_mode
        self._diff = False
        self.params = {"retries": 5}

    def sdk_call(self, operation, request):
        return operation(request)

    def exit_json(self, **kwargs):
        raise AnsibleExitJson(kwargs)

    def fail_json(self, **kwargs):
        kwargs["failed"] = True
        raise AnsibleFailJson(kwargs)


def _scale_params(**overrides):
    params = {
        "exact_count": 2,
        "count_tag": {"role": "web"},
        "image_id": "img-1",
        "instance_type": "S5.MEDIUM2",
        "instance_charge_type": "POSTPAID_BY_HOUR",
        "instance_name": "web",
        "hostname": None,
        "security_group_ids": None,
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "internet_charge_type": None,
        "internet_max_bandwidth_out": None,
        "public_ip_assigned": None,
        "password": None,
        "key_ids": None,
        "tags": {"role": "web"},
        "dry_run": False,
    }
    params.update(overrides)
    return params


def _scaling_resource(instance_id, state="RUNNING", charge_type="POSTPAID_BY_HOUR", created=None):
    data = {
        "InstanceId": instance_id,
        "InstanceName": "web",
        "InstanceState": state,
        "InstanceChargeType": charge_type,
    }
    if created is not None:
        data["CreatedTime"] = created
    resource = FakeInstance(instance_id, "web", state)
    resource._serialize = lambda allow_none=True: dict(data)
    return resource


@pytest.fixture(autouse=True)
def _no_scaling_waiters():
    with patch("ansible_collections.susunola.tencentcloud.plugins.modules.cvm_instance._wait_state",
               return_value="RUNNING"), \
            patch("ansible_collections.susunola.tencentcloud.plugins.modules.cvm_instance._wait_gone",
                  return_value=None):
        yield


def _run_validation(args):
    with patch.object(TencentCloudModule, "require_sdk", lambda self: None):
        return run(cvm_instance.run_module)


def test_exact_count_requires_count_tag():
    set_module_args(module_args(exact_count=2))
    with pytest.raises(AnsibleFailJson) as exc:
        _run_validation(None)
    assert "count_tag is required" in exc.value.args[0]["msg"]


def test_exact_count_mutually_exclusive_with_instance_id():
    set_module_args(module_args(exact_count=2, count_tag={"role": "web"}, instance_id="ins-1"))
    with pytest.raises(AnsibleFailJson) as exc:
        _run_validation(None)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_count_tag_requires_exact_count():
    set_module_args(module_args(count_tag={"role": "web"}))
    with pytest.raises(AnsibleFailJson) as exc:
        _run_validation(None)
    assert "count_tag requires exact_count" in exc.value.args[0]["msg"]


def test_exact_count_only_applies_to_present():
    set_module_args(module_args(exact_count=2, count_tag={"role": "web"}, state="running"))
    with pytest.raises(AnsibleFailJson) as exc:
        _run_validation(None)
    assert "state=present" in exc.value.args[0]["msg"]


def test_exact_count_must_be_non_negative():
    set_module_args(module_args(exact_count=-1, count_tag={"role": "web"}))
    with pytest.raises(AnsibleFailJson) as exc:
        _run_validation(None)
    assert "greater than or equal to 0" in exc.value.args[0]["msg"]


def test_exact_count_rejects_dry_run():
    set_module_args(module_args(exact_count=2, count_tag={"role": "web"}, dry_run=True))
    with pytest.raises(AnsibleFailJson) as exc:
        _run_validation(None)
    assert "dry_run" in exc.value.args[0]["msg"]


def test_describe_request_builds_tag_filters():
    request = build_describe_request(FakeScalingModels, None, None, {"role": "web"})
    assert [(item.Name, item.Values) for item in request.Filters] == [("tag:role", ["web"])]


def test_describe_request_builds_multi_tag_filters_sorted():
    request = build_describe_request(
        FakeScalingModels, None, None, {"role": "web", "tier": "api"})
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("tag:role", ["web"]), ("tag:tier", ["api"]),
    ]


def test_run_request_sets_instance_count():
    request = build_run_request(FakeScalingModels, _scale_params(instance_count=3))
    assert request.InstanceCount == 3


def test_run_request_omits_instance_count_by_default():
    request = build_run_request(FakeScalingModels, _scale_params())
    assert not hasattr(request, "InstanceCount")


def test_find_instances_by_tags_paginates():
    client = FakeScalingClient(
        [_scaling_resource("ins-a"), _scaling_resource("ins-b"), _scaling_resource("ins-c")])
    module = FakeScalingModule(client)
    matches = cvm_instance.find_instances_by_tags(module, client, FakeScalingModels, {"role": "web"})
    assert [item["InstanceId"] for item in matches] == ["ins-a", "ins-b", "ins-c"]
    assert client.describe_calls == 2


def test_find_instances_by_tags_skips_terminated():
    client = FakeScalingClient(
        [_scaling_resource("ins-a"), _scaling_resource("ins-b", state="TERMINATED"),
         _scaling_resource("ins-c")])
    module = FakeScalingModule(client)
    matches = cvm_instance.find_instances_by_tags(module, client, FakeScalingModels, {"role": "web"})
    assert [item["InstanceId"] for item in matches] == ["ins-a", "ins-c"]
    assert client.describe_calls == 2


def test_exact_count_already_met():
    client = FakeScalingClient([_scaling_resource("ins-a"), _scaling_resource("ins-b")])
    module = FakeScalingModule(client)
    with pytest.raises(AnsibleExitJson) as exc:
        cvm_instance._manage_exact_count(module, client, FakeScalingModels, _scale_params(exact_count=2))
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert payload["count"] == 2
    assert client.run_requests == []
    assert client.term_requests == []


def test_exact_count_creates_shortfall():
    client = FakeScalingClient([_scaling_resource("ins-a")])
    module = FakeScalingModule(client)
    with pytest.raises(AnsibleExitJson) as exc:
        cvm_instance._manage_exact_count(module, client, FakeScalingModels, _scale_params(exact_count=3))
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert payload["count"] == 3
    assert len(client.run_requests) == 1
    assert client.run_requests[0].InstanceCount == 2


def test_exact_count_terminates_oldest_first():
    client = FakeScalingClient([
        _scaling_resource("ins-a", created="2026-08-01 00:00:00"),
        _scaling_resource("ins-b", created="2026-08-03 00:00:00"),
        _scaling_resource("ins-c"),
    ])
    module = FakeScalingModule(client)
    with pytest.raises(AnsibleExitJson) as exc:
        cvm_instance._manage_exact_count(module, client, FakeScalingModels, _scale_params(exact_count=1))
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert payload["count"] == 1
    # Oldest first: ins-a then ins-b are removed; ins-c has no CreatedTime and
    # is never preferred for removal, so it survives.
    assert [r.InstanceIds for r in client.term_requests] == [["ins-a"], ["ins-b"]]


def test_exact_count_fails_on_prepaid_termination():
    client = FakeScalingClient([
        _scaling_resource("ins-a", created="2026-08-01 00:00:00", charge_type="PREPAID"),
        _scaling_resource("ins-b", created="2026-08-03 00:00:00"),
    ])
    module = FakeScalingModule(client)
    with pytest.raises(AnsibleFailJson) as exc:
        cvm_instance._manage_exact_count(module, client, FakeScalingModels, _scale_params(exact_count=1))
    assert "PREPAID" in exc.value.args[0]["msg"]
    assert client.term_requests == []


def test_exact_count_check_mode_reports_termination_without_api():
    client = FakeScalingClient([
        _scaling_resource("ins-a", created="2026-08-01 00:00:00"),
        _scaling_resource("ins-b", created="2026-08-03 00:00:00"),
    ])
    module = FakeScalingModule(client, check_mode=True)
    with pytest.raises(AnsibleExitJson) as exc:
        cvm_instance._manage_exact_count(module, client, FakeScalingModels, _scale_params(exact_count=1))
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert payload["terminated"] == ["ins-a"]
    assert client.term_requests == []
    assert client.run_requests == []


def test_exact_count_check_mode_reports_creation_without_api():
    client = FakeScalingClient([_scaling_resource("ins-a")])
    module = FakeScalingModule(client, check_mode=True)
    with pytest.raises(AnsibleExitJson) as exc:
        cvm_instance._manage_exact_count(module, client, FakeScalingModels, _scale_params(exact_count=3))
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert client.run_requests == []
