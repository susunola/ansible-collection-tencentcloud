"""Unit tests for the ckafka_datahub_connection write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/ckafka_datahub_connection.py`` with an in-memory fake
CKafka client whose write operations mutate the connection store, so the
module's post-write ``find`` refetch converges immediately. Connections are
matched by ``resource_id`` (via DescribeConnectResource detail) or by
name+type (via paged DescribeConnectResources); credential-like config keys
are scrubbed recursively from every output and comparison path.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_datahub_connection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeResource,
    module_args,
    run,
)

CONFIG = {"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False}

CONN = {
    "ResourceId": "cc-8b0a1c2d",
    "ResourceName": "analytics-kafka",
    "Type": "KAFKA",
    "Description": "",
    "KafkaConnectParam": copy.deepcopy(CONFIG),
}


class _NotFoundError(Exception):
    """Stand-in for the SDK's ResourceNotFound exception."""

    def get_code(self):
        return "ResourceNotFound"

    def get_request_id(self):
        return "req-nf"


class _DeserializeModel(object):
    """SDK model stand-in supporting the _deserialize round-trip."""

    def __init__(self):
        self._value = None

    def _deserialize(self, value):
        self._value = copy.deepcopy(value)
        return self

    def to_json_string(self):
        import json

        return json.dumps(self._value)


class FakeCkafkaModels(object):
    """Any model name resolves to a fresh _DeserializeModel subclass."""

    def __getattr__(self, name):
        return type(name, (_DeserializeModel,), {})


def _conn(**overrides):
    """API-shaped connection dict isolated from the shared constant."""
    item = copy.deepcopy(CONN)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "resource_id": None,
        "name": "analytics-kafka",
        "connection_type": "KAFKA",
        "description": "",
        "config": copy.deepcopy(CONFIG),
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


class FakeCkafkaClient(object):
    """In-memory CkafkaClient stand-in.

    Stores API-shaped connection dicts whose type-specific config lives under
    the field the module uses (``KafkaConnectParam`` for KAFKA, etc).
    DescribeConnectResource on an unknown id raises the ResourceNotFound
    stand-in so the module's idempotent detail() path is exercised; list
    calls honour Offset/Limit so find() pagination can be exercised.
    """

    def __init__(self, items=None):
        self.items = [copy.deepcopy(i) for i in (items or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _find(self, resource_id):
        for item in self.items:
            if item.get("ResourceId") == resource_id:
                return item
        return None

    def _config_field(self, request):
        field = mod.TYPE_FIELDS[request.Type]
        return field, getattr(request, field)._value

    def DescribeConnectResource(self, request):
        self._record("DescribeConnectResource", request)
        item = self._find(request.ResourceId)
        if item is None:
            raise _NotFoundError("connection does not exist")
        return SimpleNamespace(Result=FakeResource(dict(item)), RequestId="req-fake")

    def DescribeConnectResources(self, request):
        self._record("DescribeConnectResources", request)
        pool = [i for i in self.items if i.get("Type") == request.Type]
        page = pool[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Result=SimpleNamespace(
                ConnectResourceList=[FakeResource(dict(i)) for i in page],
                TotalCount=len(pool),
            ),
            RequestId="req-fake",
        )

    def CreateConnectResource(self, request):
        self._record("CreateConnectResource", request)
        self._next += 1
        resource_id = "cc-fake-%03d" % self._next
        field, config = self._config_field(request)
        item = {
            "ResourceId": resource_id,
            "ResourceName": request.ResourceName,
            "Type": request.Type,
            "Description": request.Description,
            field: config,
        }
        self.items.append(item)
        return SimpleNamespace(Result=SimpleNamespace(ResourceId=resource_id), RequestId="req-fake")

    def ModifyConnectResource(self, request):
        self._record("ModifyConnectResource", request)
        item = self._find(request.ResourceId)
        if item is None:
            raise _NotFoundError("connection does not exist")
        item["ResourceName"] = request.ResourceName
        item["Description"] = request.Description
        field, config = self._config_field(request)
        item[field] = config
        item["Type"] = request.Type
        return SimpleNamespace(RequestId="req-fake")

    def DeleteConnectResource(self, request):
        self._record("DeleteConnectResource", request)
        self.items = [i for i in self.items if i.get("ResourceId") != request.ResourceId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeCkafkaModels(), SimpleNamespace(CkafkaClient=object)),
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
# Table / scrub / project helper tests
# ---------------------------------------------------------------------------


def test_type_models_aliasing():
    # TDSQL variants reuse the MySQL/PostgreSQL model classes.
    assert mod.TYPE_MODELS["TDSQL_C_MYSQL"] == mod.TYPE_MODELS["MYSQL"]
    assert mod.TYPE_MODELS["TDSQL_C_POSTGRESQL"] == mod.TYPE_MODELS["POSTGRESQL"]
    # KAFKA/MQTT use the same class for create and modify.
    assert mod.TYPE_MODELS["KAFKA"][0] == mod.TYPE_MODELS["KAFKA"][1]
    assert mod.TYPE_MODELS["MQTT"][0] == mod.TYPE_MODELS["MQTT"][1]
    # Every type has a create/modify pair and a serialization field.
    for conn_type in mod.TYPE_MODELS:
        assert conn_type in mod.TYPE_FIELDS
        assert len(mod.TYPE_MODELS[conn_type]) == 2


def test_type_fields_field_names_match_create_models():
    for conn_type, (create_model, _modify_model) in mod.TYPE_MODELS.items():
        assert mod.TYPE_FIELDS[conn_type] == create_model


def test_scrub_removes_sensitive_keys_recursively():
    value = {
        "Resource": "ckafka-x",
        "Password": "hunter2",
        "Nested": {"SecretKey": "sk", "ok": 1},
        "List": [{"Token": "t", "keep": True}, {"PrivateKey": "k"}],
        "AccessKeyId": "ak",
        "credential": "c",
    }
    scrubbed = mod.scrub(value)
    assert "Password" not in scrubbed
    assert "SecretKey" not in scrubbed["Nested"]
    assert scrubbed["Nested"]["ok"] == 1
    assert scrubbed["List"][0] == {"keep": True}
    assert scrubbed["List"][1] == {}
    assert "AccessKeyId" not in scrubbed
    assert "credential" not in scrubbed
    assert scrubbed["Resource"] == "ckafka-x"


def test_scrub_is_recursive_and_returns_plain_values():
    assert mod.scrub("plain") == "plain"
    assert mod.scrub(42) == 42
    assert mod.scrub([{"password": "x", "a": [{"Secret": "y"}]}]) == [{"a": [{}]}]


def test_project_extracts_only_shape_keys():
    remote = {"Resource": "ckafka-1", "SelfBuilt": True, "OtherField": "ignored"}
    shape = mod.scrub({"Resource": "ckafka-1", "SelfBuilt": True})
    assert mod.project(remote, shape) == {"Resource": "ckafka-1", "SelfBuilt": True}


def test_project_missing_remote_keys_yield_none():
    assert mod.project({"Resource": "ckafka-1"}, {"Resource": "x", "SelfBuilt": False}) == {
        "Resource": "ckafka-1",
        "SelfBuilt": None,
    }


def test_project_list_shape_returns_value_or_empty():
    shape = {"Zones": []}
    assert mod.project({"Zones": ["ap-1"]}, shape) == {"Zones": ["ap-1"]}
    assert mod.project({}, shape) == {"Zones": []}


# ---------------------------------------------------------------------------
# Request-builder tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeCkafkaModels(), "cc-abc")
    assert request.ResourceId == "cc-abc"


def test_list_request_fields():
    request = mod.list_request(FakeCkafkaModels(), _params(name="analytics-kafka"), offset=3)
    assert request.Type == "KAFKA"
    assert request.SearchWord == "analytics-kafka"
    assert request.Offset == 3
    assert request.Limit == 1000


def test_create_request_populates_type_specific_param():
    models = FakeCkafkaModels()
    p = _params(name="analytics-kafka", description="Analytics destination", config={"Resource": "ckafka-x", "SelfBuilt": True})
    request = mod.create_request(models, p)
    assert request.ResourceName == "analytics-kafka"
    assert request.Type == "KAFKA"
    assert request.Description == "Analytics destination"
    param = request.KafkaConnectParam
    assert param._value == {"Resource": "ckafka-x", "SelfBuilt": True}


def test_create_request_uses_alias_field_for_tdsql():
    models = FakeCkafkaModels()
    p = _params(connection_type="TDSQL_C_MYSQL", config={"Resource": "cdb-x"})
    request = mod.create_request(models, p)
    assert request.MySQLConnectParam._value == {"Resource": "cdb-x"}


def test_update_request_fields():
    models = FakeCkafkaModels()
    p = _params(name="renamed", description="d", config={"Resource": "ckafka-y"})
    request = mod.update_request(models, p, "cc-abc")
    assert request.ResourceId == "cc-abc"
    assert request.ResourceName == "renamed"
    assert request.Description == "d"
    assert request.Type == "KAFKA"
    assert request.KafkaConnectParam._value == {"Resource": "ckafka-y"}


def test_delete_request_fields():
    request = mod.delete_request(FakeCkafkaModels(), "cc-abc")
    assert request.ResourceId == "cc-abc"


# ---------------------------------------------------------------------------
# detail / find tests
# ---------------------------------------------------------------------------


def test_detail_returns_scrubbed_result(monkeypatch):
    fake = FakeCkafkaClient([_conn(KafkaConnectParam={"Resource": "ckafka-x", "Password": "hunter2"})])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(resource_id="cc-8b0a1c2d"))
    value = mod.detail(module, fake, FakeCkafkaModels(), "cc-8b0a1c2d")
    assert value["ResourceName"] == "analytics-kafka"
    assert "Password" not in value["KafkaConnectParam"]


def test_detail_not_found_returns_none(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(resource_id="cc-missing"))
    assert mod.detail(module, fake, FakeCkafkaModels(), "cc-missing") is None


def test_detail_propagates_non_not_found_errors(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)

    def explode(request):
        raise RuntimeError("backend exploded")

    monkeypatch.setattr(fake, "DescribeConnectResource", explode)
    module = FakeModule(_params(resource_id="cc-x"))
    with pytest.raises(RuntimeError, match="backend exploded"):
        mod.detail(module, fake, FakeCkafkaModels(), "cc-x")


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="no-such-connection"))
    assert mod.find(module, fake, FakeCkafkaModels(), module.params) is None


def test_find_matches_by_name_and_type(monkeypatch):
    fake = FakeCkafkaClient([_conn(), _conn(ResourceId="cc-2", ResourceName="other", Type="MYSQL")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="analytics-kafka"))
    value = mod.find(module, fake, FakeCkafkaModels(), module.params)
    assert value["ResourceId"] == "cc-8b0a1c2d"
    # A different type with the same name is NOT a match.
    fake2 = FakeCkafkaClient([_conn(Type="MYSQL")])
    _make_module(monkeypatch, fake2)
    module2 = FakeModule(_params(name="analytics-kafka", connection_type="MYSQL"))
    value2 = mod.find(module2, fake2, FakeCkafkaModels(), module2.params)
    assert value2 is None or value2["Type"] == "MYSQL"


def test_find_by_resource_id_prefers_detail(monkeypatch):
    fake = FakeCkafkaClient([_conn(ResourceName="renamed-elsewhere")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(resource_id="cc-8b0a1c2d", name="ignored"))
    value = mod.find(module, fake, FakeCkafkaModels(), module.params)
    assert value["ResourceId"] == "cc-8b0a1c2d"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeConnectResource") == 1
    assert "DescribeConnectResources" not in names


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeCkafkaClient([_conn(ResourceId="cc-1"), _conn(ResourceId="cc-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="analytics-kafka"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeCkafkaModels(), module.params)
    assert "multiple CKafka Datahub connections matched" in exc.value.args[0]["msg"]


def test_find_paginates_until_match(monkeypatch):
    items = [_conn(ResourceId="cc-bulk-%04d" % i, ResourceName="bulk-%04d" % i) for i in range(1000)]
    items.append(_conn(ResourceId="cc-last", ResourceName="analytics-kafka"))
    fake = FakeCkafkaClient(items)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="analytics-kafka"))
    value = mod.find(module, fake, FakeCkafkaModels(), module.params)
    assert value["ResourceId"] == "cc-last"
    list_calls = [c for c in fake.calls if c[0] == "DescribeConnectResources"]
    assert len(list_calls) == 2  # page 1 (1000) + page 2 (1)
    assert list_calls[0][1].Offset == 0
    assert list_calls[1][1].Offset == 1000


def test_find_paginates_to_end_returns_none(monkeypatch):
    items = [_conn(ResourceId="cc-bulk-%04d" % i, ResourceName="bulk-%04d" % i) for i in range(1500)]
    fake = FakeCkafkaClient(items)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="analytics-kafka"))
    assert mod.find(module, fake, FakeCkafkaModels(), module.params) is None
    list_calls = [c for c in fake.calls if c[0] == "DescribeConnectResources"]
    assert len(list_calls) == 2


# ---------------------------------------------------------------------------
# comparable / desired tests
# ---------------------------------------------------------------------------


def test_comparable_projects_remote_config_to_shape():
    remote = {
        "ResourceName": "analytics-kafka",
        "Type": "KAFKA",
        "Description": "note",
        "KafkaConnectParam": {"Resource": "ckafka-x", "SelfBuilt": False, "Password": "hunter2"},
    }
    p = _params(description="note", config={"Resource": "ckafka-x", "SelfBuilt": False})
    value = mod.comparable(remote, p)
    assert value == {
        "ResourceName": "analytics-kafka",
        "Type": "KAFKA",
        "Description": "note",
        "Config": {"Resource": "ckafka-x", "SelfBuilt": False},
    }


def test_comparable_normalises_missing_description():
    remote = {"ResourceName": "x", "Type": "KAFKA", "Description": None, "KafkaConnectParam": {}}
    value = mod.comparable(remote, _params(description=""))
    assert value["Description"] == ""


def test_desired_scrubs_config():
    p = _params(description="note", config={"Resource": "ckafka-x", "Token": "t"})
    assert mod.desired(p) == {
        "ResourceName": "analytics-kafka",
        "Type": "KAFKA",
        "Description": "note",
        "Config": {"Resource": "ckafka-x"},
    }


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced():
    module_args()  # no name / connection_type / config
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_connection_type_choices_enforced():
    module_args(state="present", name="x", connection_type="NOT_A_TYPE", config={"Resource": "r"})
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeCkafkaModels(), SimpleNamespace(CkafkaClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="analytics-kafka", connection_type="KAFKA", config={"Resource": "ckafka-x"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_connection(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        description="Analytics destination",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["ResourceId"] == "cc-fake-001"
    assert result["connection"]["ResourceName"] == "analytics-kafka"
    assert result["connection"]["Type"] == "KAFKA"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeConnectResources") == 1  # find before create
    assert names.count("CreateConnectResource") == 1
    assert names.count("DescribeConnectResource") == 1  # refetch after create


def test_present_creation_scrubs_credentials_from_output(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False, "Password": "hunter2"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    text = str(result["connection"])
    assert "Password" not in text
    assert "hunter2" not in text
    assert result["connection"]["KafkaConnectParam"] == {"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False}


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False},
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"]["ResourceId"] == "cc-8b0a1c2d"
    names = [c[0] for c in fake.calls]
    assert "CreateConnectResource" not in names
    assert "ModifyConnectResource" not in names


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        description="Analytics destination",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["Description"] == "Analytics destination"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyConnectResource") == 1
    update = [c for c in fake.calls if c[0] == "ModifyConnectResource"][0][1]
    assert update.ResourceId == "cc-8b0a1c2d"
    assert update.Description == "Analytics destination"


def test_present_config_drift_triggers_update(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": True},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["KafkaConnectParam"]["SelfBuilt"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyConnectResource") == 1
    update = [c for c in fake.calls if c[0] == "ModifyConnectResource"][0][1]
    assert update.KafkaConnectParam._value["SelfBuilt"] is True


def test_present_immutable_type_change_with_resource_id_fails(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        resource_id="cc-8b0a1c2d",
        name="analytics-kafka",
        connection_type="MYSQL",
        config={"Resource": "cdb-x"},
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["Type"] == {"before": "KAFKA", "after": "MYSQL"}
    assert not any(n.startswith("Modify") for n, request in fake.calls)


def test_present_resource_id_not_found_fails(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        resource_id="cc-missing",
        name="analytics-kafka",
        connection_type="KAFKA",
        config={"Resource": "ckafka-x"},
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "resource_id was not found; omit it to create" in exc.value.args[0]["msg"]
    assert "CreateConnectResource" not in [c[0] for c in fake.calls]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None  # no real resource in check mode
    assert not any("CreateConnectResource" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="analytics-kafka",
        connection_type="KAFKA",
        description="new description",
        config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported connection is the pre-change state.
    assert result["connection"]["Description"] == ""
    assert not any(n.startswith("Modify") for n, request in fake.calls)


def test_absent_removes_connection(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="analytics-kafka", connection_type="KAFKA", config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteConnectResource") == 1
    delete = [c for c in fake.calls if c[0] == "DeleteConnectResource"][0][1]
    assert delete.ResourceId == "cc-8b0a1c2d"
    assert fake.items == []


def test_absent_by_resource_id_removes(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", resource_id="cc-8b0a1c2d", name="analytics-kafka", connection_type="KAFKA",
                config={"Resource": "ckafka-x"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeConnectResource") == 1
    assert names.count("DeleteConnectResource") == 1


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="missing", connection_type="KAFKA", config={"Resource": "ckafka-x"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"] is None
    assert not any("DeleteConnectResource" == c[0] for c in fake.calls)


def test_absent_not_found_by_resource_id_is_noop(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", resource_id="cc-missing", name="analytics-kafka", connection_type="KAFKA",
                config={"Resource": "ckafka-x"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"] is None
    assert not any("DeleteConnectResource" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_conn()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="analytics-kafka", connection_type="KAFKA",
                config={"Resource": "ckafka-8b0a1c2d", "SelfBuilt": False})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is not None  # pre-change state reported
    assert not any("DeleteConnectResource" == c[0] for c in fake.calls)
    assert len(fake.items) == 1
