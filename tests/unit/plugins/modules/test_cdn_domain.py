"""Unit tests for the cdn_domain write module (helpers + run_module).

Covers the add / delete / start / stop / reconcile flows of
``plugins/modules/cdn_domain.py`` with an in-memory fake CDN client,
following the collection's module test harness (see harness.py).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdn_domain as cdn
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = {
    "Domain": "cdn.example.com",
    "Cname": "cdn.example.com.cdn.dnsv1.com",
    "Status": "online",
    "ProjectId": 0,
    "ServiceType": "web",
    "Area": "mainland",
    "Origin": {
        "Origins": ["origin.example.com"],
        "OriginType": "domain",
        "OriginPullProtocol": "http",
        "BackupOrigins": [],
    },
}

WRITE_OPS = ("AddCdnDomain", "DeleteCdnDomain", "StartCdnDomain", "StopCdnDomain", "UpdateDomainConfig")


def _domain(**overrides):
    """Return a domain fixture isolated from the shared DOMAIN constant."""
    item = copy.deepcopy(DOMAIN)
    item.update(overrides)
    return item


class FakeCdnClient(object):
    """In-memory CDN client that mutates a small domain store."""

    def __init__(self, domains=None):
        self.domains = [copy.deepcopy(domain) for domain in (domains or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_domain(self, domain):
        return next(item for item in self.domains if item["Domain"] == domain)

    def DescribeDomains(self, request):
        self._record("DescribeDomains", request)
        return SimpleNamespace(Domains=[FakeResource(item) for item in self.domains])

    def AddCdnDomain(self, request):
        self._record("AddCdnDomain", request)
        origin = request.Origin
        item = {
            "Domain": request.Domain,
            "Cname": request.Domain + ".cdn.dnsv1.com",
            "Status": "online",
            "ServiceType": request.ServiceType,
            "Origin": {
                "Origins": list(origin.Origins),
                "OriginType": origin.OriginType,
                "OriginPullProtocol": getattr(origin, "OriginPullProtocol", None),
                "BackupOrigins": list(getattr(origin, "BackupOrigins", None) or []),
            },
        }
        if hasattr(request, "ProjectId"):
            item["ProjectId"] = request.ProjectId
        if hasattr(request, "Area"):
            item["Area"] = request.Area
        self.domains.append(item)
        return SimpleNamespace()

    def DeleteCdnDomain(self, request):
        self._record("DeleteCdnDomain", request)
        self.domains = [item for item in self.domains if item["Domain"] != request.Domain]
        return SimpleNamespace()

    def StartCdnDomain(self, request):
        self._record("StartCdnDomain", request)
        self._by_domain(request.Domain)["Status"] = "online"
        return SimpleNamespace()

    def StopCdnDomain(self, request):
        self._record("StopCdnDomain", request)
        self._by_domain(request.Domain)["Status"] = "offline"
        return SimpleNamespace()

    def UpdateDomainConfig(self, request):
        self._record("UpdateDomainConfig", request)
        item = self._by_domain(request.Domain)
        for key in ("ServiceType", "ProjectId", "Area"):
            if hasattr(request, key):
                item[key] = getattr(request, key)
        if hasattr(request, "Origin"):
            origin = request.Origin
            for key in ("Origins", "OriginType", "OriginPullProtocol"):
                if hasattr(origin, key):
                    item["Origin"][key] = list(getattr(origin, key)) if key == "Origins" else getattr(origin, key)
            if hasattr(origin, "BackupOrigins"):
                item["Origin"]["BackupOrigins"] = list(origin.BackupOrigins)
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helper functions that only need sdk_call."""

    def __init__(self):
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)


@pytest.fixture
def client(monkeypatch):
    fake = FakeCdnClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cdn, "_load_cdn",
        lambda: (FakeModels(), SimpleNamespace(CdnClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_build_describe_request_filters_by_domain():
    request = cdn.build_describe_request(FakeModels(), "cdn.example.com")
    assert request.Limit == 100
    assert request.Filters[0].Name == "domain"
    assert request.Filters[0].Value == ["cdn.example.com"]


def test_build_describe_request_without_domain_omits_filters():
    request = cdn.build_describe_request(FakeModels(), None)
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_first_returns_head_or_none():
    assert cdn._first([1, 2]) == 1
    assert cdn._first([]) is None


def test_find_domain_matches():
    module = FakeModule()
    client = FakeCdnClient(domains=[_domain()])
    found = cdn.find_domain(module, client, FakeModels(), "cdn.example.com")
    assert found["Domain"] == "cdn.example.com"
    assert found["Origin"]["Origins"] == ["origin.example.com"]
    assert [name for name, request in client.calls] == ["DescribeDomains"]


def test_find_domain_missing_returns_none():
    module = FakeModule()
    client = FakeCdnClient()
    assert cdn.find_domain(module, client, FakeModels(), "cdn.example.com") is None


def test_find_domain_ignores_non_matching_first_result():
    module = FakeModule()
    client = FakeCdnClient(domains=[_domain(Domain="other.example.com")])
    assert cdn.find_domain(module, client, FakeModels(), "cdn.example.com") is None


def _add_params(**overrides):
    params = {
        "domain": "cdn.example.com",
        "service_type": "web",
        "origins": ["origin.example.com"],
        "origin_type": "domain",
        "origin_protocol": "http",
        "backup_origins": ["backup.example.com"],
        "project_id": 100,
        "area": "global",
    }
    params.update(overrides)
    return params


def test_build_add_request_sets_all_fields():
    request = cdn.build_add_request(FakeModels(), _add_params())
    assert request.Domain == "cdn.example.com"
    assert request.ServiceType == "web"
    assert request.Origin.Origins == ["origin.example.com"]
    assert request.Origin.OriginType == "domain"
    assert request.Origin.OriginPullProtocol == "http"
    assert request.Origin.BackupOrigins == ["backup.example.com"]
    assert request.ProjectId == 100
    assert request.Area == "global"


def test_build_add_request_omits_optional_fields():
    request = cdn.build_add_request(FakeModels(), _add_params(
        origin_protocol=None, backup_origins=None, project_id=None, area=None,
    ))
    assert request.Domain == "cdn.example.com"
    assert request.ServiceType == "web"
    assert request.Origin.Origins == ["origin.example.com"]
    assert request.Origin.OriginType == "domain"
    assert not hasattr(request.Origin, "OriginPullProtocol")
    assert not hasattr(request.Origin, "BackupOrigins")
    assert not hasattr(request, "ProjectId")
    assert not hasattr(request, "Area")


def test_origin_builder_keeps_explicit_empty_backup():
    # The update builder keeps an explicitly empty backup list while the add
    # builder treats an empty list as absent.
    origin = cdn._origin(FakeModels(), _add_params(backup_origins=[]))
    assert origin.Origins == ["origin.example.com"]
    assert origin.OriginType == "domain"
    assert origin.OriginPullProtocol == "http"
    assert origin.BackupOrigins == []


def test_origin_builder_skips_missing_protocol():
    origin = cdn._origin(FakeModels(), _add_params(origin_protocol=None))
    assert not hasattr(origin, "OriginPullProtocol")


def test_build_update_request_sets_origin_and_optionals():
    request = cdn.build_update_request(FakeModels(), _add_params())
    assert request.Domain == "cdn.example.com"
    assert request.Origin.Origins == ["origin.example.com"]
    assert request.Origin.BackupOrigins == ["backup.example.com"]
    assert request.ServiceType == "web"
    assert request.ProjectId == 100
    assert request.Area == "global"


def test_build_update_request_without_changes_sets_domain_only():
    request = cdn.build_update_request(FakeModels(), _add_params(
        service_type=None, project_id=None, area=None, origins=None,
        origin_type=None, origin_protocol=None, backup_origins=None,
    ))
    assert request.Domain == "cdn.example.com"
    assert not hasattr(request, "Origin")
    assert not hasattr(request, "ServiceType")
    assert not hasattr(request, "ProjectId")
    assert not hasattr(request, "Area")


def test_desired_config_maps_supplied_fields():
    desired = cdn._desired_config(_add_params())
    assert desired == {
        "ServiceType": "web",
        "ProjectId": 100,
        "Area": "global",
        "Origin": {
            "Origins": ["origin.example.com"],
            "OriginType": "domain",
            "OriginPullProtocol": "http",
            "BackupOrigins": ["backup.example.com"],
        },
    }


def test_desired_config_empty_when_no_fields():
    assert cdn._desired_config(_add_params(
        service_type=None, project_id=None, area=None, origins=None,
        origin_type=None, origin_protocol=None, backup_origins=None,
    )) == {}


def test_current_config_projects_origin_subset():
    desired = {"ServiceType": "web", "Origin": {"Origins": "any", "OriginPullProtocol": "any"}}
    current = {
        "ServiceType": "web", "ProjectId": 0,
        "Origin": {
            "Origins": ["origin.example.com"], "OriginType": "domain",
            "OriginPullProtocol": "http", "BackupOrigins": [],
        },
    }
    result = cdn._current_config(current, desired)
    assert result == {
        "ServiceType": "web",
        "Origin": {"Origins": ["origin.example.com"], "OriginPullProtocol": "http"},
    }


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_domain_required(client):
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdn.run_module)
    assert "domain is required" in exc.value.args[0]["msg"]


def test_absent_missing_domain_is_unchanged(client):
    module_args(state="absent", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_domain(client):
    client.domains = [_domain()]
    module_args(state="absent", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert result["domain"] is None
    assert any(name == "DeleteCdnDomain" for name, request in client.calls)
    assert client.domains == []


def test_check_mode_absent_makes_no_writes(client):
    client.domains = [_domain()]
    module_args(state="absent", domain="cdn.example.com", _ansible_check_mode=True)
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "Would delete" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_running_missing_domain_fails(client):
    module_args(state="running", domain="cdn.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdn.run_module)
    assert "Domain not found" in exc.value.args[0]["msg"]


def test_running_online_is_unchanged(client):
    client.domains = [_domain()]
    module_args(state="running", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is False
    assert "already online" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_running_starts_offline_domain(client):
    client.domains = [_domain(Status="offline")]
    module_args(state="running", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "started" in result["msg"]
    assert any(name == "StartCdnDomain" for name, request in client.calls)
    assert client.domains[0]["Status"] == "online"


def test_check_mode_running_makes_no_writes(client):
    client.domains = [_domain(Status="offline")]
    module_args(state="running", domain="cdn.example.com", _ansible_check_mode=True)
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "Would start" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_stopped_offline_is_unchanged(client):
    client.domains = [_domain(Status="offline")]
    module_args(state="stopped", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is False
    assert "already stopped" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_stopped_stops_online_domain(client):
    client.domains = [_domain()]
    module_args(state="stopped", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "stopped" in result["msg"]
    assert any(name == "StopCdnDomain" for name, request in client.calls)
    assert client.domains[0]["Status"] == "offline"


def test_check_mode_stopped_makes_no_writes(client):
    client.domains = [_domain()]
    module_args(state="stopped", domain="cdn.example.com", _ansible_check_mode=True)
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "Would stop" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_add_requires_service_type_origins_and_origin_type(client):
    module_args(state="present", domain="cdn.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdn.run_module)
    payload = exc.value.args[0]
    assert "required when adding" in payload["msg"]
    assert "service_type" in payload["msg"]
    assert "origins" in payload["msg"]
    assert "origin_type" in payload["msg"]


def test_add_creates_domain(client):
    module_args(
        state="present", domain="cdn.example.com", service_type="web",
        origins=["origin.example.com"], origin_type="domain",
        origin_protocol="http", backup_origins=["backup.example.com"],
        project_id=100, area="global",
    )
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "added" in result["msg"]
    assert any(name == "AddCdnDomain" for name, request in client.calls)
    assert len(client.domains) == 1
    assert client.domains[0]["Domain"] == "cdn.example.com"
    assert client.domains[0]["ProjectId"] == 100
    assert result["domain"]["Domain"] == "cdn.example.com"


def test_check_mode_add_makes_no_writes(client):
    module_args(
        state="present", domain="cdn.example.com", service_type="web",
        origins=["origin.example.com"], origin_type="domain",
        _ansible_check_mode=True,
    )
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "Would add" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_matching_domain_is_unchanged(client):
    client.domains = [_domain()]
    module_args(state="present", domain="cdn.example.com")
    result = run(cdn.run_module)
    assert result["changed"] is False
    assert "up to date" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_updates_origin_protocol(client):
    client.domains = [_domain()]
    module_args(state="present", domain="cdn.example.com", origin_protocol="https")
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    update = [(name, request) for name, request in client.calls if name == "UpdateDomainConfig"]
    assert len(update) == 1
    assert update[0][1].Origin.OriginPullProtocol == "https"
    assert client.domains[0]["Origin"]["OriginPullProtocol"] == "https"
    assert client.domains[0]["Origin"]["Origins"] == ["origin.example.com"]


def test_present_updates_origins(client):
    client.domains = [_domain()]
    module_args(state="present", domain="cdn.example.com", origins=["new.example.com"])
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert client.domains[0]["Origin"]["Origins"] == ["new.example.com"]
    assert client.domains[0]["Origin"]["OriginType"] == "domain"


def test_present_updates_project_id(client):
    client.domains = [_domain()]
    module_args(state="present", domain="cdn.example.com", project_id=100)
    result = run(cdn.run_module)
    assert result["changed"] is True
    update = [(name, request) for name, request in client.calls if name == "UpdateDomainConfig"]
    assert update[0][1].ProjectId == 100
    assert client.domains[0]["ProjectId"] == 100


def test_present_updates_area(client):
    client.domains = [_domain()]
    module_args(state="present", domain="cdn.example.com", area="overseas")
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert client.domains[0]["Area"] == "overseas"


def test_check_mode_update_makes_no_writes(client):
    client.domains = [_domain()]
    module_args(state="present", domain="cdn.example.com", origin_protocol="https", _ansible_check_mode=True)
    result = run(cdn.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert result["diff"]["before"]["Origin"]["OriginPullProtocol"] == "http"
    assert result["diff"]["after"]["Origin"]["OriginPullProtocol"] == "https"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("cdn api exploded")

    client.DescribeDomains = boom
    module_args(state="present", domain="cdn.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdn.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "cdn api exploded" in payload["error"]
