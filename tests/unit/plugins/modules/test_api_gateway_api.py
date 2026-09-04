"""Unit tests for the api_gateway_api write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/api_gateway_api.py`` with an in-memory fake API Gateway
client whose write operations mutate the API store, so the module's
post-write ``find`` refetch converges immediately. APIs are matched by
``api_id`` (DescribeApi, not-found swallowed) or by name across the paged
DescribeApisStatus followed by a detail fetch. There is no immutable guard:
a name drift simply triggers ModifyApi. The MOCK service type carries
``ServiceMockReturnMessage`` on the wire request; HTTP omits it. In check
mode the module reports ``api=None`` for a would-be create (no refetch) and
the pre-change API for a would-be update.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_api as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

API = {
    "ApiId": "api-1",
    "ApiName": "health",
    "ApiDesc": "",
    "AuthType": "NONE",
    "ServiceType": "MOCK",
    "ServiceTimeout": 15,
    "EnableCORS": False,
    "RequestConfig": {"Path": "/", "Method": "ANY"},
    "ServiceMockReturnMessage": "{}",
}


def _api(**overrides):
    """API-shaped detail dict isolated from the shared constant."""
    item = copy.deepcopy(API)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "service_id": "service-1",
        "api_id": None,
        "name": "health",
        "path": "/",
        "method": "ANY",
        "description": "",
        "auth_type": "NONE",
        "service_type": "MOCK",
        "service_timeout": 15,
        "mock_response": "{}",
        "enable_cors": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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


class _NotFound(RuntimeError):
    """SDK-style not-found exception understood by ``is_not_found``."""

    def get_code(self):
        return "ResourceNotFound.NotFound"


class FakeApigatewayClient(object):
    """In-memory ApigatewayClient stand-in for APIs.

    Stores API-shaped detail dicts. DescribeApi resolves by ApiId and raises
    a not-found error for unknown ids (mirroring the SDK); DescribeApisStatus
    pages summary entries over the store honouring Offset/Limit; write
    operations mutate the store so post-write refetches converge.
    """

    def __init__(self, apis=None):
        self.apis = [copy.deepcopy(a) for a in (apis or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "api-%d" % self._next_id

    def DescribeApi(self, request):
        self._record("DescribeApi", request)
        for stored in self.apis:
            if stored.get("ApiId") == request.ApiId:
                return SimpleNamespace(Result=FakeResource(dict(stored)), RequestId="req-fake")
        raise _NotFound("API %s not found" % request.ApiId)

    def DescribeApisStatus(self, request):
        self._record("DescribeApisStatus", request)
        page = self.apis[request.Offset : request.Offset + request.Limit]
        items = [FakeResource({"ApiId": a["ApiId"], "ApiName": a["ApiName"]}) for a in page]
        return SimpleNamespace(
            Result=SimpleNamespace(ApiIdStatusSet=items, TotalCount=len(self.apis)),
            RequestId="req-fake",
        )

    def CreateApi(self, request):
        self._record("CreateApi", request)
        api_id = self._new_id()
        api = {
            "ApiId": api_id,
            "ApiName": request.ApiName,
            "ApiDesc": request.ApiDesc,
            "AuthType": request.AuthType,
            "ServiceType": request.ServiceType,
            "ServiceTimeout": request.ServiceTimeout,
            "EnableCORS": request.EnableCORS,
            "RequestConfig": {"Path": request.RequestConfig.Path, "Method": request.RequestConfig.Method},
        }
        if request.ServiceType == "MOCK":
            api["ServiceMockReturnMessage"] = request.ServiceMockReturnMessage
        self.apis.append(api)
        return SimpleNamespace(Result=SimpleNamespace(ApiId=api_id), RequestId="req-fake")

    def ModifyApi(self, request):
        self._record("ModifyApi", request)
        for stored in self.apis:
            if stored.get("ApiId") != request.ApiId:
                continue
            stored["ApiName"] = request.ApiName
            stored["ApiDesc"] = request.ApiDesc
            stored["AuthType"] = request.AuthType
            stored["ServiceType"] = request.ServiceType
            stored["ServiceTimeout"] = request.ServiceTimeout
            stored["EnableCORS"] = request.EnableCORS
            stored["RequestConfig"] = {"Path": request.RequestConfig.Path, "Method": request.RequestConfig.Method}
            if request.ServiceType == "MOCK":
                stored["ServiceMockReturnMessage"] = request.ServiceMockReturnMessage
            else:
                stored.pop("ServiceMockReturnMessage", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteApi(self, request):
        self._record("DeleteApi", request)
        self.apis = [a for a in self.apis if a.get("ApiId") != request.ApiId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ApigatewayClient=object)),
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
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_request_config_fields():
    value = mod.request_config(FakeModels(), "/health", "GET")
    assert value.Path == "/health"
    assert value.Method == "GET"


def test_build_list_with_name_filter():
    request = mod.build_list(FakeModels(), "service-1", "health")
    assert request.ServiceId == "service-1"
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.Filters[0].Name == "ApiName"
    assert request.Filters[0].Values == ["health"]


def test_build_list_without_name_filter():
    request = mod.build_list(FakeModels(), "service-1", None, offset=100)
    assert not hasattr(request, "Filters")  # name filter only when searching
    assert request.Offset == 100


def test_build_get_fields():
    request = mod.build_get(FakeModels(), "service-1", "api-9")
    assert request.ServiceId == "service-1"
    assert request.ApiId == "api-9"


def test_apply_request_mock_full():
    request = mod.apply_request(FakeModels().CreateApiRequest(), FakeModels(), _params(mock_response='{"ok": true}'), api_id="api-7")
    assert request.ServiceId == "service-1"
    assert request.ApiName == "health"
    assert request.ApiDesc == ""
    assert request.AuthType == "NONE"
    assert request.ServiceType == "MOCK"
    assert request.ServiceTimeout == 15
    assert request.Protocol == "http"
    assert request.ApiType == "NORMAL"
    assert request.RequestConfig.Path == "/"
    assert request.RequestConfig.Method == "ANY"
    assert request.EnableCORS is False
    assert request.ServiceMockReturnMessage == '{"ok": true}'
    assert request.ApiId == "api-7"


def test_apply_request_http_omits_mock_message():
    request = mod.apply_request(FakeModels().CreateApiRequest(), FakeModels(), _params(service_type="HTTP"))
    assert request.ServiceType == "HTTP"
    assert not hasattr(request, "ServiceMockReturnMessage")


def test_apply_request_create_has_no_api_id():
    request = mod.apply_request(FakeModels().CreateApiRequest(), FakeModels(), _params())
    assert not hasattr(request, "ApiId")


def test_desired_defaults():
    assert mod.desired(_params()) == {
        "ApiName": "health",
        "ApiDesc": "",
        "AuthType": "NONE",
        "ServiceType": "MOCK",
        "ServiceTimeout": 15,
        "EnableCORS": False,
        "Path": "/",
        "Method": "ANY",
    }


def test_comparable_reads_request_config():
    value = mod.comparable(_api())
    assert value["ApiName"] == "health"
    assert value["ApiDesc"] == ""
    assert value["Path"] == "/"
    assert value["Method"] == "ANY"
    assert value["EnableCORS"] is False


def test_comparable_normalises_desc_and_cors():
    value = mod.comparable(_api(ApiDesc=None, EnableCORS=1, RequestConfig={"Path": "/v1", "Method": "POST"}))
    assert value["ApiDesc"] == ""
    assert value["EnableCORS"] is True
    assert value["Path"] == "/v1"
    assert value["Method"] == "POST"


def test_comparable_missing_request_config():
    value = mod.comparable(_api(RequestConfig=None))
    assert value["Path"] is None
    assert value["Method"] is None


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_api_id(monkeypatch):
    fake = FakeApigatewayClient([_api(), _api(ApiId="api-2", ApiName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(api_id="api-2", name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["ApiId"] == "api-2"
    assert [c[0] for c in fake.calls] == ["DescribeApi"]


def test_find_by_api_id_not_found_returns_none(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(api_id="api-ghost", name=None))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeApigatewayClient([_api(ApiName="other"), _api()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="health"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["ApiId"] == "api-1"
    assert [c[0] for c in fake.calls] == ["DescribeApisStatus", "DescribeApi"]


def test_find_by_name_no_match_returns_none(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert [c[0] for c in fake.calls] == ["DescribeApisStatus"]


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeApigatewayClient([_api(), _api(ApiId="api-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="health"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple APIs have the requested name" in payload["msg"]
    assert payload["name"] == "health"


def test_find_by_name_paginates_past_100(monkeypatch):
    apis = [_api(ApiId="bulk-%04d" % i, ApiName="bulk-%04d" % i) for i in range(101)]
    apis.append(_api())
    fake = FakeApigatewayClient(apis)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="health"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["ApiId"] == "api-1"
    status_calls = [c for c in fake.calls if c[0] == "DescribeApisStatus"]
    assert len(status_calls) == 2  # pages of 100
    assert [c[1].Offset for c in status_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(service_id="service-1")  # neither api_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_mock_api(monkeypatch):
    fake = FakeApigatewayClient()
    _make_module(monkeypatch, fake)
    _run_args(mock_response='{"ok": true}')
    result = run(mod.run_module)
    assert result["changed"] is True
    api = result["api"]
    assert api["ApiId"] == "api-101"
    assert api["ApiName"] == "health"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeApi") == 1  # post-create refetch
    assert names.count("CreateApi") == 1
    create = [c for c in fake.calls if c[0] == "CreateApi"][0][1]
    assert create.ServiceId == "service-1"
    assert create.ServiceMockReturnMessage == '{"ok": true}'
    assert create.Protocol == "http"
    assert create.ApiType == "NORMAL"


def test_present_creates_http_api_without_mock_message(monkeypatch):
    fake = FakeApigatewayClient()
    _make_module(monkeypatch, fake)
    _run_args(service_type="HTTP", enable_cors=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["ServiceType"] == "HTTP"
    assert "ServiceMockReturnMessage" not in result["api"]
    create = [c for c in fake.calls if c[0] == "CreateApi"][0][1]
    assert not hasattr(create, "ServiceMockReturnMessage")
    assert create.EnableCORS is True


def test_present_requires_name_when_id_absent(monkeypatch):
    fake = FakeApigatewayClient()
    _make_module(monkeypatch, fake)
    _run_args(api_id="api-ghost", name=None)  # id given but absent
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating an API" in exc.value.args[0]["msg"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["api"]["ApiId"] == "api-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyApi" not in names
    assert "CreateApi" not in names


def test_present_path_method_drift_triggers_update(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args(api_id="api-1", path="/v2", method="POST")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["RequestConfig"] == {"Path": "/v2", "Method": "POST"}
    modify = [c for c in fake.calls if c[0] == "ModifyApi"][0][1]
    assert modify.ApiId == "api-1"
    assert modify.RequestConfig.Path == "/v2"
    assert modify.RequestConfig.Method == "POST"


def test_present_rename_by_id_triggers_update(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args(api_id="api-1", name="renamed")  # identified by id, name drifts
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["ApiName"] == "renamed"
    modify = [c for c in fake.calls if c[0] == "ModifyApi"][0][1]
    assert modify.ApiId == "api-1"
    assert modify.ApiName == "renamed"


def test_present_service_type_drift_triggers_update(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args(api_id="api-1", service_type="HTTP")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["ServiceType"] == "HTTP"
    assert "ServiceMockReturnMessage" not in result["api"]
    modify = [c for c in fake.calls if c[0] == "ModifyApi"][0][1]
    assert not hasattr(modify, "ServiceMockReturnMessage")


def test_present_enable_cors_drift_triggers_update(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args(api_id="api-1", enable_cors=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["EnableCORS"] is True
    modify = [c for c in fake.calls if c[0] == "ModifyApi"][0][1]
    assert modify.EnableCORS is True


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"] is None  # no refetch in check mode
    assert not any("CreateApi" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(api_id="api-1", path="/v2").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["ApiId"] == "api-1"  # pre-change API reported
    assert not any("ModifyApi" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ApigatewayClient=object)),
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


def test_absent_deletes_api(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="health")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteApi"][0][1]
    assert delete.ServiceId == "service-1"
    assert delete.ApiId == "api-1"
    assert fake.apis == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["api"] is None
    assert not any("DeleteApi" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient([_api()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api"]["ApiId"] == "api-1"  # pre-change API reported
    assert not any("DeleteApi" == c[0] for c in fake.calls)
    assert len(fake.apis) == 1
