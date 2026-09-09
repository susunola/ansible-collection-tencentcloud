"""Unit tests for the teo_security_template_binding write module (run_module flows).

The module reconciles the exact set of acceleration domains bound to one
EdgeOne web security template. Domains absent from the current binding are
attached with ``BindSecurityTemplateToEntity`` and domains that must be
removed are detached with the same API but an ``unbind-*`` operate value
whose suffix is controlled by ``unbind_policy``. There is no create/delete
lifecycle: the template already exists and only its entity set is edited.

Scenario matrix:

* duplicate ``domains`` fail validation before any SDK call
* an already-matching binding set is idempotent, ignoring other templates,
  other zones and inactive (non-online/process/pending) statuses
* missing domains are bound, extra domains are unbound, and a mixed drift
  performs both in one pass
* ``unbind_policy=use-default`` switches the operate suffix
* check mode reports the diff without writing
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_template_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ZONE_ID = "zone-abc123"
TEMPLATE_ID = "temp-1001"


def _binding(entity, status="online", **overrides):
    item = {"TemplateId": TEMPLATE_ID, "ZoneId": ZONE_ID, "Entity": entity, "Status": status}
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "zone_id": ZONE_ID,
        "template_id": TEMPLATE_ID,
        "domains": ["app.example.com", "api.example.com"],
    }
    params.update(overrides)
    return module_args(**params)


class FakeTeoClient(object):
    """In-memory EdgeOne client storing per-(template, zone) entity bindings."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(t) for t in (bindings or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeSecurityTemplateBindings(self, request):
        self._record("DescribeSecurityTemplateBindings", request)
        zones_by_template = {}
        for b in self.bindings:
            zones_by_template.setdefault(b["TemplateId"], {}).setdefault(b["ZoneId"], []).append(b)
        templates = []
        for template_id, zones in zones_by_template.items():
            scopes = []
            for zone_id, items in zones.items():
                statuses = [FakeResource({"Entity": it["Entity"], "Status": it["Status"]}) for it in items]
                scopes.append(FakeResource({"ZoneId": zone_id, "EntityStatus": statuses}))
            templates.append(FakeResource({"TemplateId": template_id, "TemplateScope": scopes}))
        return SimpleNamespace(SecurityTemplate=templates, TotalCount=len(self.bindings))

    def BindSecurityTemplateToEntity(self, request):
        self._record("BindSecurityTemplateToEntity", request)
        template_id = getattr(request, "TemplateId", None)
        zone_id = getattr(request, "ZoneId", None)
        entities = list(getattr(request, "Entities", None) or [])
        operate = getattr(request, "Operate", None) or "bind"
        for entity in entities:
            self.bindings = [
                b
                for b in self.bindings
                if not (b["TemplateId"] == template_id and b["ZoneId"] == zone_id and b["Entity"] == entity)
            ]
            if operate == "bind":
                self.bindings.append(
                    {"TemplateId": template_id, "ZoneId": zone_id, "Entity": entity, "Status": "online"}
                )
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TeoClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _entities(bindings):
    return sorted(b["Entity"] for b in bindings)


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_duplicate_domains_fail_validation(monkeypatch):
    fake = FakeTeoClient(bindings=[])
    _make_module(monkeypatch, fake)
    _args(domains=["app.example.com", "app.example.com"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domains must not contain duplicates" in exc.value.args[0]["msg"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_matching_binding_set_is_idempotent(monkeypatch):
    fake = FakeTeoClient(
        bindings=[
            _binding("api.example.com"),
            _binding("app.example.com"),
            _binding("other-zone.example.com", ZoneId="zone-other"),
            _binding("other-template.example.com", TemplateId="temp-9999"),
            _binding("zombie.example.com", Status="offline"),
        ]
    )
    _make_module(monkeypatch, fake)
    # unsorted input and unsorted store order both normalize through sorting
    _args(domains=["app.example.com", "api.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c for c, unused in fake.calls] == ["DescribeSecurityTemplateBindings"]


def test_inactive_status_is_not_counted_as_bound(monkeypatch):
    fake = FakeTeoClient(bindings=[_binding("api.example.com"), _binding("app.example.com", Status="offline")])
    _make_module(monkeypatch, fake)
    _args(domains=["api.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is False
    # the offline binding must not be unbound
    assert "BindSecurityTemplateToEntity" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_binds_missing_domains(monkeypatch):
    fake = FakeTeoClient(bindings=[_binding("db.example.com", TemplateId="temp-9999")])
    _make_module(monkeypatch, fake)
    _args(overwrite=False, domains=["app.example.com", "api.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert _entities(result["bindings"]) == ["api.example.com", "app.example.com"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeSecurityTemplateBindings"
    assert ops[-1] == "DescribeSecurityTemplateBindings"
    bind_call = dict((name, request) for name, request in fake.calls)["BindSecurityTemplateToEntity"]
    assert bind_call.Operate == "bind"
    assert bind_call.OverWrite is False
    assert sorted(bind_call.Entities) == ["api.example.com", "app.example.com"]


def test_unbinds_extra_domains_with_keep_policy(monkeypatch):
    fake = FakeTeoClient(bindings=[_binding("api.example.com"), _binding("app.example.com"), _binding("old.example.com")])
    _make_module(monkeypatch, fake)
    _args(domains=["api.example.com", "app.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert _entities(result["bindings"]) == ["api.example.com", "app.example.com"]
    unbind_call = dict((name, request) for name, request in fake.calls)["BindSecurityTemplateToEntity"]
    assert unbind_call.Operate == "unbind-keep-policy"
    assert unbind_call.Entities == ["old.example.com"]


def test_unbind_use_default_policy(monkeypatch):
    fake = FakeTeoClient(bindings=[_binding("old.example.com")])
    _make_module(monkeypatch, fake)
    _args(unbind_policy="use-default", domains=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["bindings"] == []
    unbind_call = dict((name, request) for name, request in fake.calls)["BindSecurityTemplateToEntity"]
    assert unbind_call.Operate == "unbind-use-default"


def test_mixed_drift_binds_and_unbinds_in_one_pass(monkeypatch):
    fake = FakeTeoClient(
        bindings=[_binding("api.example.com"), _binding("app.example.com"), _binding("old.example.com")]
    )
    _make_module(monkeypatch, fake)
    _args(domains=["app.example.com", "new.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert _entities(result["bindings"]) == ["app.example.com", "new.example.com"]
    ops = [(name, request) for name, request in fake.calls if name == "BindSecurityTemplateToEntity"]
    assert len(ops) == 3
    assert ops[0][1].Operate == "bind"
    assert sorted(ops[0][1].Entities) == ["new.example.com"]
    unbind_ops = sorted(op[1].Entities[0] for op in ops[1:])
    assert unbind_ops == ["api.example.com", "old.example.com"]


def test_check_mode_reports_diff_without_writing(monkeypatch):
    fake = FakeTeoClient(bindings=[_binding("api.example.com")])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, domains=["api.example.com", "app.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert "BindSecurityTemplateToEntity" not in [c for c, unused in fake.calls]
    assert _entities(fake.bindings) == ["api.example.com"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSecurityTemplateBindings(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
