"""Unit tests for the mqtt_instance write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/mqtt_instance.py`` with an in-memory fake MQTT client whose
write operations mutate the instance store, so the module's post-write
``find`` refetch converges immediately. Instances are matched by
``instance_id`` or by ``InstanceName`` across the DescribeInstanceList page,
then hydrated through DescribeInstance; creation-only settings (vpcs /
enable_public / ip_rules / tags / billing) never trigger updates, and
``instance_type`` is immutable.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mqtt_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "mqtt-x1",
    "InstanceName": "prod-mqtt",
    "InstanceType": "PRO",
    "SkuCode": "pro_2k",
    "Remark": "",
    "AuthorizationPolicy": None,
    "MessageRate": None,
}


def _instance(**overrides):
    """API-shaped instance dict isolated from the shared constant."""
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "instance_id": None,
        "name": None,
        "instance_type": None,
        "sku_code": None,
        "remark": "",
        "vpcs": [],
        "enable_public": False,
        "bandwidth": None,
        "ip_rules": [],
        "tags": None,
        "pay_mode": 0,
        "period_months": 1,
        "auto_renew": True,
        "authorization_policy": None,
        "message_rate": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter.

    None-valued keys are dropped so no-default choices params (instance_type)
    are simply not passed instead of being rejected by Ansible validation.
    """
    return _module_args(None, **extra)


def _module_args(check_mode, **extra):
    """module_args() with check mode toggled and None-valued keys dropped."""
    args = {key: value for key, value in _params().items() if value is not None}
    args.update(extra)
    if check_mode:
        args["_ansible_check_mode"] = True
    return module_args(**args)


def _vpc(vpc_id="vpc-a", subnet_id="subnet-b"):
    return {"vpc_id": vpc_id, "subnet_id": subnet_id}


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


class FakeMqttClient(object):
    """In-memory MqttClient stand-in.

    Stores full detail-shaped instance dicts. DescribeInstanceList pages the
    store (id + name projection), DescribeInstance returns the stored detail
    wrapped so ``_serialize`` works, and the write operations mutate the
    store so post-write refetches converge.
    """

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(i) for i in (instances or [])]
        self.calls = []
        self._next_id = 10000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeInstanceList(self, request):
        self._record("DescribeInstanceList", request)
        page = self.instances[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Data=[FakeResource({"InstanceId": i["InstanceId"], "InstanceName": i["InstanceName"]}) for i in page],
            RequestId="req-fake",
        )

    def DescribeInstance(self, request):
        self._record("DescribeInstance", request)
        for i in self.instances:
            if i["InstanceId"] == request.InstanceId:
                return FakeResource(dict(i))
        return FakeResource({})

    def CreateInstance(self, request):
        self._record("CreateInstance", request)
        self._next_id += 1
        instance_id = "mqtt-fake-%05d" % self._next_id
        self.instances.append(
            {
                "InstanceId": instance_id,
                "InstanceName": request.Name,
                "InstanceType": request.InstanceType,
                "SkuCode": request.SkuCode,
                "Remark": request.Remark,
                "AuthorizationPolicy": None,
                "MessageRate": None,
            }
        )
        return SimpleNamespace(InstanceId=instance_id, RequestId="req-fake")

    def ModifyInstance(self, request):
        self._record("ModifyInstance", request)
        for stored in self.instances:
            if stored["InstanceId"] != request.InstanceId:
                continue
            stored["InstanceName"] = request.Name
            stored["Remark"] = request.Remark
            stored["SkuCode"] = request.SkuCode
            stored["AuthorizationPolicy"] = request.AuthorizationPolicy
            stored["MessageRate"] = request.MessageRate
        return SimpleNamespace(RequestId="req-fake")

    def DeleteInstance(self, request):
        self._record("DeleteInstance", request)
        self.instances = [i for i in self.instances if i["InstanceId"] != request.InstanceId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MqttClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder helper tests
# ---------------------------------------------------------------------------


def test_list_request_fields():
    request = mod.list_request(FakeModels())
    assert request.Offset == 0
    assert request.Limit == 100


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), "mqtt-x1")
    assert request.InstanceId == "mqtt-x1"


def test_items_capitalises_underscore_keys():
    items = mod._items(FakeModels(), FakeModels().VpcInfo, [{"vpc_id": "vpc-a", "subnet_id": "subnet-b"}])
    assert len(items) == 1
    assert items[0].VpcId == "vpc-a"
    assert items[0].SubnetId == "subnet-b"


def test_items_empty():
    assert mod._items(FakeModels(), FakeModels().VpcInfo, None) == []
    assert mod._items(FakeModels(), FakeModels().VpcInfo, []) == []


def test_create_request_fields():
    request = mod.create_request(
        FakeModels(),
        _params(
            name="prod-mqtt",
            instance_type="PRO",
            sku_code="pro_2k",
            remark="prod",
            vpcs=[_vpc()],
            enable_public=True,
            bandwidth=20,
            ip_rules=[{"ip": "203.0.113.0/24", "allow": False, "remark": "deny"}],
            pay_mode=1,
            period_months=3,
            auto_renew=False,
        ),
    )
    assert request.Name == "prod-mqtt"
    assert request.InstanceType == "PRO"
    assert request.SkuCode == "pro_2k"
    assert request.Remark == "prod"
    assert len(request.VpcList) == 1
    assert request.VpcList[0].VpcId == "vpc-a"
    assert request.EnablePublic is True
    assert request.Bandwidth == 20
    assert len(request.IpRules) == 1
    assert request.IpRules[0].Ip == "203.0.113.0/24"
    assert request.IpRules[0].Allow is False
    assert request.PayMode == 1
    assert request.TimeSpan == 3
    assert request.RenewFlag == 0


def test_create_request_tags_sorted():
    request = mod.create_request(FakeModels(), _params(tags={"b": "2", "a": "1"}))
    assert [t.TagKey for t in request.TagList] == ["a", "b"]
    assert request.TagList[0].TagValue == "1"


def test_update_request_uses_current_fallbacks():
    request = mod.update_request(FakeModels(), _params(name=None, sku_code=None), _instance())
    assert request.InstanceId == "mqtt-x1"
    assert request.Name == "prod-mqtt"  # falls back to current InstanceName
    assert request.SkuCode == "pro_2k"
    assert request.Remark == ""
    assert request.AuthorizationPolicy is None
    assert request.MessageRate is None


def test_update_request_applies_explicit_fields():
    request = mod.update_request(FakeModels(), _params(name="renamed", sku_code="pro_4k", authorization_policy=True, message_rate=500), _instance())
    assert request.Name == "renamed"
    assert request.SkuCode == "pro_4k"
    assert request.AuthorizationPolicy is True
    assert request.MessageRate == 500


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "mqtt-x1")
    assert request.InstanceId == "mqtt-x1"


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name_hydrates_detail(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="prod-mqtt"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["InstanceId"] == "mqtt-x1"
    assert value["InstanceName"] == "prod-mqtt"
    names = [c[0] for c in fake.calls]
    assert names == ["DescribeInstanceList", "DescribeInstance"]


def test_find_by_instance_id(monkeypatch):
    fake = FakeMqttClient([_instance(), _instance(InstanceId="mqtt-x2", InstanceName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(instance_id="mqtt-x2"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["InstanceId"] == "mqtt-x2"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeMqttClient([_instance(), _instance(InstanceId="mqtt-x2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="prod-mqtt"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple MQTT instances matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither instance_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_enable_public_requires_bandwidth():
    module_args(state="present", instance_id="mqtt-x1", enable_public=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "bandwidth" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MqttClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(instance_id="mqtt-x1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    _run_args(instance_id="mqtt-none")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["name", "instance_type", "sku_code", "vpcs"]


def test_present_creates_instance(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    _run_args(name="prod-mqtt", instance_type="PRO", sku_code="pro_2k", vpcs=[_vpc()], remark="prod")
    result = run(mod.run_module)
    assert result["changed"] is True
    instance = result["instance"]
    assert instance["InstanceId"] == "mqtt-fake-10001"
    assert instance["InstanceName"] == "prod-mqtt"
    assert instance["Remark"] == "prod"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeInstanceList") == 2  # find + refetch
    assert names.count("CreateInstance") == 1
    create = [c for c in fake.calls if c[0] == "CreateInstance"][0][1]
    assert create.Name == "prod-mqtt"
    assert create.InstanceType == "PRO"
    assert create.VpcList[0].VpcId == "vpc-a"


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-mqtt")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "mqtt-x1"
    names = [c[0] for c in fake.calls]
    assert "ModifyInstance" not in names
    assert "CreateInstance" not in names


def test_present_remark_drift_triggers_update(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-mqtt", remark="moved to new region")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Remark"] == "moved to new region"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyInstance") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyInstance"][0][1]
    assert modify.InstanceId == "mqtt-x1"
    assert modify.Name == "prod-mqtt"


def test_present_instance_id_only_update(monkeypatch):
    # instance_id-only reference with a matching instance -> no drift when
    # every managed field equals the current values.
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(instance_id="mqtt-x1")
    result = run(mod.run_module)
    assert result["changed"] is False


def test_present_authorization_and_rate_update(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(instance_id="mqtt-x1", authorization_policy=True, message_rate=1000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["AuthorizationPolicy"] is True
    assert result["instance"]["MessageRate"] == 1000
    modify = [c for c in fake.calls if c[0] == "ModifyInstance"][0][1]
    assert modify.AuthorizationPolicy is True
    assert modify.MessageRate == 1000


def test_present_instance_type_is_immutable(monkeypatch):
    fake = FakeMqttClient([_instance(InstanceType="BASIC")])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-mqtt", instance_type="PRO")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "instance_type is immutable" in payload["msg"]
    assert payload["before"] == "BASIC"
    assert payload["after"] == "PRO"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(name="prod-mqtt", instance_type="PRO", sku_code="pro_2k", vpcs=[_vpc()]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] == {"InstanceName": "prod-mqtt", "InstanceType": "PRO", "SkuCode": "pro_2k", "Remark": ""}
    assert not any("CreateInstance" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(name="prod-mqtt", remark="new remark").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Remark"] == ""  # pre-change state
    assert not any("ModifyInstance" == c[0] for c in fake.calls)


def test_absent_removes_instance(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", instance_id="mqtt-x1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteInstance"][0][1]
    assert delete.InstanceId == "mqtt-x1"
    assert fake.instances == []


def test_absent_by_name_removes(monkeypatch):
    fake = FakeMqttClient([_instance(), _instance(InstanceId="mqtt-x2", InstanceName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="other")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [i["InstanceId"] for i in fake.instances] == ["mqtt-x1"]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert not any("DeleteInstance" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent", instance_id="mqtt-x1").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert not any("DeleteInstance" == c[0] for c in fake.calls)
    assert len(fake.instances) == 1
