"""Unit tests for the trabbit_serverless_queue write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/trabbit_serverless_queue.py`` with an in-memory fake
Trabbit client whose write operations mutate the queue store, so the
module's post-write ``find`` refetch converges immediately. Queues are
located by name within a virtual host; the create defaults (classic /
durable / non-auto-delete), the four mutable fields (remark, message TTL,
dead-letter exchange / routing key) and the 16-field immutable guard are
exercised along with check-mode dry runs.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import trabbit_serverless_queue as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

QUEUE = {
    "QueueName": "order-workers",
    "VirtualHost": "production",
    "InstanceId": "amqp-8b0a1c2d",
    "QueueType": "classic",
    "Durable": True,
    "AutoDelete": False,
    "Remark": "",
    "MessageTTL": 60000,
    "AutoExpire": None,
    "MaxLength": None,
    "MaxLengthBytes": None,
    "DeliveryLimit": None,
    "OverflowBehaviour": None,
    "DeadLetterExchange": "orders-dlx",
    "DeadLetterRoutingKey": "retry.key",
    "SingleActiveConsumer": False,
    "MaximumPriority": None,
    "LazyMode": False,
    "MasterLocator": None,
    "MaxInMemoryLength": None,
    "MaxInMemoryBytes": None,
    "Node": None,
    "DeadLetterStrategy": None,
    "QueueLeaderLocator": None,
    "QuorumInitialGroupSize": None,
}


def _queue(**overrides):
    """Return a queue fixture isolated from the shared constant."""
    item = copy.deepcopy(QUEUE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included).

    NOTE: queue_type / overflow_behaviour / master_locator /
    dead_letter_strategy / queue_leader_locator carry choices but no
    default. Ansible only validates choices for keys the user explicitly
    passed, so omitted (absent) keys are safe but an explicit ``None`` is
    rejected. Tests therefore never pre-fill them; pass a concrete value
    when a scenario needs it.
    """
    params = {
        "state": "present",
        "instance_id": "amqp-8b0a1c2d",
        "virtual_host": "production",
        "name": "order-workers",
        "durable": None,
        "auto_delete": None,
        "remark": "",
        "message_ttl": None,
        "auto_expire": None,
        "max_length": None,
        "max_length_bytes": None,
        "delivery_limit": None,
        "single_active_consumer": None,
        "maximum_priority": None,
        "lazy_mode": None,
        "max_in_memory_length": None,
        "max_in_memory_bytes": None,
        "node": None,
        "dead_letter_exchange": None,
        "dead_letter_routing_key": None,
        "quorum_initial_group_size": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


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


class FakeTrabbitClient(object):
    """In-memory Trabbit client that mutates a small queue store."""

    def __init__(self, queues=None):
        self.queues = [copy.deepcopy(q) for q in (queues or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeRabbitMQServerlessQueues(self, request):
        self._record("DescribeRabbitMQServerlessQueues", request)
        search = getattr(request, "SearchWord", None)
        items = self.queues if search is None else [q for q in self.queues if q.get("QueueName") == search]
        return SimpleNamespace(
            QueueInfoList=[FakeResource({"QueueName": q["QueueName"]}) for q in items],
            TotalCount=len(items),
        )

    def DescribeRabbitMQServerlessQueueDetail(self, request):
        self._record("DescribeRabbitMQServerlessQueueDetail", request)
        for item in self.queues:
            if item.get("QueueName") == request.QueueName and item.get("VirtualHost") == request.VirtualHost:
                return FakeResource(dict(item, RequestId="req-fake"))
        return FakeResource({"RequestId": "req-fake"})

    def CreateRabbitMQServerlessQueue(self, request):
        self._record("CreateRabbitMQServerlessQueue", request)
        item = {
            field: getattr(request, field, None) for field in mod.FIELDS
        }
        self.queues.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRabbitMQServerlessQueue(self, request):
        self._record("ModifyRabbitMQServerlessQueue", request)
        for item in self.queues:
            if item.get("QueueName") == request.QueueName and item.get("VirtualHost") == request.VirtualHost:
                for field in mod.MUTABLE:
                    value = getattr(request, field, None)
                    if value is not None:
                        item[field] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQServerlessQueue(self, request):
        self._record("DeleteRabbitMQServerlessQueue", request)
        self.queues = [
            q
            for q in self.queues
            if not (q.get("QueueName") == request.QueueName and q.get("VirtualHost") == request.VirtualHost)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, params=None):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)),
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


def test_describe_request_fields_and_pagination():
    request = mod.describe_request(FakeModels(), _params(), offset=50)
    assert request.InstanceId == "amqp-8b0a1c2d"
    assert request.VirtualHost == "production"
    assert request.SearchWord == "order-workers"
    assert request.Offset == 50
    assert request.Limit == 100


def test_detail_request_fields():
    request = mod.detail_request(FakeModels(), _params())
    assert request.InstanceId == "amqp-8b0a1c2d"
    assert request.VirtualHost == "production"
    assert request.QueueName == "order-workers"


def test_create_request_applies_defaults():
    request = mod.create_request(FakeModels(), _params())
    assert request.QueueType == "classic"
    assert request.Durable is True
    assert request.AutoDelete is False
    assert request.Remark == ""


def test_create_request_copies_argument_fields():
    p = _params(
        queue_type="quorum",
        durable=False,
        auto_delete=True,
        remark="workers",
        message_ttl=86400000,
        max_length=1000,
        dead_letter_exchange="orders-dlx",
        single_active_consumer=True,
        max_in_memory_bytes=4096,
        node="rabbit@node-1",
    )
    request = mod.create_request(FakeModels(), p)
    assert request.QueueType == "quorum"
    assert request.Durable is False
    assert request.AutoDelete is True
    assert request.Remark == "workers"
    assert request.MessageTTL == 86400000
    assert request.MaxLength == 1000
    assert request.DeadLetterExchange == "orders-dlx"
    assert request.SingleActiveConsumer is True
    assert request.MaxInMemoryBytes == 4096
    assert request.Node == "rabbit@node-1"
    assert getattr(request, "MaxLengthBytes", None) is None
    assert getattr(request, "AutoExpire", None) is None


def test_update_request_uses_params_and_current_fallback():
    current = _queue()
    request = mod.update_request(FakeModels(), _params(message_ttl=1234), current)
    assert request.InstanceId == "amqp-8b0a1c2d"
    assert request.VirtualHost == "production"
    assert request.QueueName == "order-workers"
    assert request.MessageTTL == 1234
    # Dead-letter fields not given -> inherited from remote state.
    assert request.DeadLetterExchange == "orders-dlx"
    assert request.DeadLetterRoutingKey == "retry.key"


def test_update_request_omitted_ttl_falls_back_to_current():
    request = mod.update_request(FakeModels(), _params(), _queue(MessageTTL=90000))
    assert request.MessageTTL == 90000
    assert request.Remark == ""


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "amqp-8b0a1c2d"
    assert request.VirtualHost == "production"
    assert request.QueueName == "order-workers"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="missing-queue"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_match_returns_detail_without_request_id(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["QueueName"] == "order-workers"
    assert value["MessageTTL"] == 60000
    assert "RequestId" not in value


def test_immutable_table_covers_creation_arguments():
    # Creation-only arguments (type, durability, auto-delete) must also be
    # protected once the queue exists.
    assert "QueueType" in mod.IMMUTABLE
    assert "Durable" in mod.IMMUTABLE
    assert "AutoDelete" in mod.IMMUTABLE
    assert "AutoExpire" in mod.IMMUTABLE
    assert "MaxLength" in mod.IMMUTABLE
    # The four genuinely mutable fields are excluded.
    assert set(mod.MUTABLE) == {"Remark", "MessageTTL", "DeadLetterExchange", "DeadLetterRoutingKey"}


def test_comparable_normalizes_remark():
    value = mod.comparable(_queue())
    assert value["QueueName"] == "order-workers"
    assert value["QueueType"] == "classic"
    assert value["MessageTTL"] == 60000
    assert value["Remark"] == ""


def test_comparable_missing_remark_defaults_empty():
    value = mod.comparable({})
    assert value["Remark"] == ""
    assert value["QueueName"] is None
    assert value["Durable"] is None


def test_desired_new_resource_applies_defaults():
    target = mod.desired(_params())
    assert target["QueueType"] == "classic"
    assert target["Durable"] is True
    assert target["AutoDelete"] is False
    assert target["QueueName"] == "order-workers"
    assert target["VirtualHost"] == "production"
    assert target["Remark"] == ""


def test_desired_new_resource_uses_explicit_values():
    p = _params(queue_type="quorum", durable=False, auto_delete=True, message_ttl=5000)
    target = mod.desired(p)
    assert target["QueueType"] == "quorum"
    assert target["Durable"] is False
    assert target["AutoDelete"] is True
    assert target["MessageTTL"] == 5000


def test_desired_keeps_current_when_param_omitted():
    current = _queue(MessageTTL=90000, DeadLetterRoutingKey="key-a")
    target = mod.desired(_params(), current)
    assert target["MessageTTL"] == 90000
    assert target["DeadLetterRoutingKey"] == "key-a"
    assert target["QueueType"] == "classic"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def test_present_creates_queue_with_defaults(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="amqp-8b0a1c2d", virtual_host="production", name="order-workers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["QueueName"] == "order-workers"
    assert result["queue"]["QueueType"] == "classic"
    assert result["queue"]["Durable"] is True
    assert result["queue"]["AutoDelete"] is False
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeRabbitMQServerlessQueues") == 2  # find + refetch
    assert "DescribeRabbitMQServerlessQueueDetail" in names
    assert names.count("CreateRabbitMQServerlessQueue") == 1
    assert not any("ModifyRabbitMQServerlessQueue" == n for n in names)


def test_present_create_records_quorum_arguments(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="amqp-8b0a1c2d", virtual_host="production", name="order-workers",
                queue_type="quorum", durable=False, auto_delete=True, message_ttl=86400000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["QueueType"] == "quorum"
    assert result["queue"]["Durable"] is False
    assert result["queue"]["MessageTTL"] == 86400000
    create = [c for c in fake.calls if c[0] == "CreateRabbitMQServerlessQueue"][0][1]
    assert create.AutoDelete is True


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="amqp-8b0a1c2d", virtual_host="production", name="order-workers")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["queue"]["QueueName"] == "order-workers"
    names = [c[0] for c in fake.calls]
    assert "CreateRabbitMQServerlessQueue" not in names
    assert "ModifyRabbitMQServerlessQueue" not in names


def test_present_drift_on_mutable_remark_triggers_update(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="amqp-8b0a1c2d", virtual_host="production",
                name="order-workers", remark="workers-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["Remark"] == "workers-v2"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyRabbitMQServerlessQueue") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessQueue"][0][1]
    # TTL inherited from remote state so it is not clobbered.
    assert modify.MessageTTL == 60000
    assert modify.DeadLetterExchange == "orders-dlx"


def test_present_immutable_max_length_change_fails(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="amqp-8b0a1c2d", virtual_host="production",
                name="order-workers", max_length=5000)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["MaxLength"] == {"before": None, "after": 5000}
    assert not any("ModifyRabbitMQServerlessQueue" == c[0] for c in fake.calls)


def test_present_immutable_queue_type_change_fails(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="amqp-8b0a1c2d", virtual_host="production",
                name="order-workers", queue_type="quorum")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"]["QueueType"] == {"before": "classic", "after": "quorum"}


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", instance_id="amqp-8b0a1c2d",
                virtual_host="production", name="order-workers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"] is None  # no write means nothing to report
    assert not any("CreateRabbitMQServerlessQueue" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", instance_id="amqp-8b0a1c2d",
                virtual_host="production", name="order-workers", remark="workers-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported queue is the pre-change state.
    assert result["queue"]["Remark"] == ""
    assert not any("ModifyRabbitMQServerlessQueue" == c[0] for c in fake.calls)


def test_absent_removes_queue(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="amqp-8b0a1c2d", virtual_host="production", name="order-workers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"] is None
    assert [c[0] for c in fake.calls].count("DeleteRabbitMQServerlessQueue") == 1
    assert fake.queues == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="amqp-8b0a1c2d", virtual_host="production", name="order-workers")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["queue"] is None
    assert not any("DeleteRabbitMQServerlessQueue" == c[0] for c in fake.calls)


def test_absent_check_mode_reports_current(monkeypatch):
    fake = FakeTrabbitClient([_queue()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", instance_id="amqp-8b0a1c2d",
                virtual_host="production", name="order-workers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["QueueName"] == "order-workers"
    assert not any("DeleteRabbitMQServerlessQueue" == c[0] for c in fake.calls)
    assert len(fake.queues) == 1
