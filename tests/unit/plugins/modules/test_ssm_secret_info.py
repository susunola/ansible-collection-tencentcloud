# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the ssm_secret_info read module.

The module answers exactly one of two questions. With ``secret_name`` it
returns that one Secret's metadata under ``secret``; without it, it walks the
inventory and returns ``secrets``/``total_count``/``truncated``. The tests pin
both shapes -- including that the two modes are mutually exclusive with every
list-only option, and that the page bounds guard fires before any client is
built. The module also promises never to retrieve Secret values, so the list
mode result is asserted to be the metadata the API returned and nothing more,
and the exact mode result to be exactly the documented metadata payload with
the request id lifted out of it. Pagination is asserted end-to-end: the
recorded call count, the offsets, the stop on the API's own "no more results"
signal, and the ``truncated`` flag when ``max_pages`` runs the budget out.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_secret_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

METADATA = [
    {"SecretName": "prod/database", "Description": "production database", "Status": "Enabled"},
    {"SecretName": "prod/api-key", "Description": "api key", "Status": "Enabled"},
]

INVENTORY = [{"SecretName": "secret-%d" % index} for index in range(1, 6)]

SECRET = {
    "SecretName": "prod/database",
    "Description": "production database",
    "Status": "Enabled",
    "RequestId": "req-exact",
}

# Fields that would carry Secret material if the module ever read it.
SECRET_VALUE_FIELDS = ("SecretString", "SecretValue", "SecretBinary", "PlainText")


class FakeSsmClient(object):
    """Records every call and serves canned ListSecrets pages.

    ``pages`` holds one list of metadata dicts per ``ListSecrets`` call; calls
    past the scripted pages get an empty page, which is the API's own "no more
    results" signal. ``total`` is what the fake reports as ``TotalCount``, and
    defaults to the number of scripted items.
    """

    def __init__(self, secret=None, pages=None, total=None):
        self.secret = dict(secret if secret is not None else SECRET)
        self.pages = [list(page) for page in (pages if pages is not None else [METADATA])]
        self.total = sum(len(page) for page in self.pages) if total is None else total
        self.calls = []

    def DescribeSecret(self, request):
        self.calls.append(("DescribeSecret", request))
        return FakeResource(self.secret)

    def ListSecrets(self, request):
        self.calls.append(("ListSecrets", request))
        index = len([name for name, _request in self.calls if name == "ListSecrets"]) - 1
        page = self.pages[index] if index < len(self.pages) else []
        return FakeResource({"SecretMetadatas": [FakeResource(item) for item in page],
                             "TotalCount": self.total,
                             "RequestId": "req-list-%d" % (index + 1)})

    def operations(self):
        return [name for name, _request in self.calls]


def _wire(monkeypatch, client):
    """Point the module at the fake client and a no-op SDK check."""
    monkeypatch.setattr(mod.TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load",
                        lambda: (FakeModels(), SimpleNamespace(SsmClient=object())))
    monkeypatch.setattr(mod.TencentCloudModule, "create_client",
                        lambda self, cls, endpoint: client)


# ---------------------------------------------------------------------------
# exact mode
# ---------------------------------------------------------------------------

def test_exact_mode_returns_the_metadata(monkeypatch):
    """The documented exact-mode payload: the Secret metadata under ``secret``
    and nothing else -- no inventory keys, and the request id reported
    separately."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    result = run(mod.run_module)

    expected = dict(SECRET)
    expected.pop("RequestId")

    assert result["changed"] is False
    assert result["secret"] == expected
    assert result["request_id"] == "req-exact"
    for key in ("secrets", "total_count", "truncated"):
        assert key not in result
    assert not set(SECRET_VALUE_FIELDS) & set(result["secret"])


def test_exact_mode_sends_the_secret_name_and_does_not_list(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    run(mod.run_module)

    assert client.operations() == ["DescribeSecret"]
    name, request = client.calls[0]
    assert name == "DescribeSecret"
    assert request.SecretName == "prod/database"


# ---------------------------------------------------------------------------
# list mode
# ---------------------------------------------------------------------------

def test_list_mode_returns_the_inventory(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args()
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["secrets"] == METADATA
    assert result["total_count"] == 2
    assert result["truncated"] is False
    assert result["request_id"] == "req-list-1"
    assert "secret" not in result


def test_list_mode_returns_no_secret_material(monkeypatch):
    """The module promises metadata only: the inventory is passed through as
    the API returned it, no value-bearing field is added, and the run reaches
    for no value-reading API at all."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args()
    result = run(mod.run_module)

    assert client.operations() == ["ListSecrets"]
    assert result["secrets"] == METADATA
    for item in result["secrets"]:
        assert not set(SECRET_VALUE_FIELDS) & set(item)


def test_list_mode_requests_the_first_page_with_the_defaults(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args()
    run(mod.run_module)

    assert len(client.calls) == 1
    assert (client.calls[0][1].Offset, client.calls[0][1].Limit) == (0, 100)
    # descending creation-time ordering and the unfiltered state are the
    # documented defaults.
    assert (client.calls[0][1].OrderType, client.calls[0][1].State) == (0, 0)


def test_list_mode_sends_the_filters(monkeypatch):
    client = FakeSsmClient(pages=[[]], total=0)
    _wire(monkeypatch, client)
    module_args(state_filter=2, search_name="prod", secret_type=1, product_name="cdb",
                encrypt_type=1, instance_id="ins-abc", order="ascending",
                tag_filters={"environment": ["production"]})
    run(mod.run_module)

    request = client.calls[0][1]
    assert (request.OrderType, request.State) == (1, 2)
    assert request.SearchSecretName == "prod"
    assert request.SecretType == 1
    assert request.ProductName == "cdb"
    assert request.EncryptType == 1
    assert request.InstanceID == "ins-abc"
    assert [(item.TagKey, item.TagValue) for item in request.TagFilters] == \
        [("environment", ["production"])]


# ---------------------------------------------------------------------------
# pagination
# ---------------------------------------------------------------------------

def test_pagination_walks_every_page(monkeypatch):
    client = FakeSsmClient(pages=[[INVENTORY[0], INVENTORY[1]],
                                  [INVENTORY[2], INVENTORY[3]],
                                  [INVENTORY[4]]], total=5)
    _wire(monkeypatch, client)
    module_args(page_size=2)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert client.operations() == ["ListSecrets"] * 3
    assert [request.Offset for _name, request in client.calls] == [0, 2, 4]
    assert [request.Limit for _name, request in client.calls] == [2, 2, 2]
    assert [item["SecretName"] for item in result["secrets"]] == \
        [item["SecretName"] for item in INVENTORY]
    assert result["total_count"] == 5
    assert result["truncated"] is False
    assert result["request_id"] == "req-list-3"


def test_pagination_stops_on_the_api_no_more_results_signal(monkeypatch):
    """An empty page ends the walk even when TotalCount claims there is more,
    and that is not truncation: the API itself said there was nothing left."""
    client = FakeSsmClient(pages=[[INVENTORY[0], INVENTORY[1]], []], total=10)
    _wire(monkeypatch, client)
    module_args(page_size=2)
    result = run(mod.run_module)

    assert client.operations() == ["ListSecrets"] * 2
    assert [request.Offset for _name, request in client.calls] == [0, 2]
    assert len(result["secrets"]) == 2
    assert result["total_count"] == 10
    assert result["truncated"] is False
    assert result["request_id"] == "req-list-2"


def test_pagination_reports_truncation_when_max_pages_runs_out(monkeypatch):
    client = FakeSsmClient(pages=[[INVENTORY[0], INVENTORY[1]],
                                  [INVENTORY[2], INVENTORY[3]],
                                  [INVENTORY[4]]], total=5)
    _wire(monkeypatch, client)
    module_args(page_size=2, max_pages=2)
    result = run(mod.run_module)

    assert client.operations() == ["ListSecrets"] * 2
    assert len(result["secrets"]) == 4
    assert result["total_count"] == 5
    assert result["truncated"] is True


def test_smallest_accepted_page_budget_is_honoured(monkeypatch):
    client = FakeSsmClient(pages=[[INVENTORY[0]], [INVENTORY[1]]], total=2)
    _wire(monkeypatch, client)
    module_args(page_size=1, max_pages=1)
    result = run(mod.run_module)

    assert len(client.calls) == 1
    assert (client.calls[0][1].Offset, client.calls[0][1].Limit) == (0, 1)
    assert len(result["secrets"]) == 1
    assert result["total_count"] == 2
    assert result["truncated"] is True


def test_an_empty_inventory_is_reported_as_empty(monkeypatch):
    client = FakeSsmClient(pages=[], total=0)
    _wire(monkeypatch, client)
    module_args()
    result = run(mod.run_module)

    assert client.operations() == ["ListSecrets"]
    assert result["changed"] is False
    assert result["secrets"] == []
    assert result["total_count"] == 0
    assert result["truncated"] is False


# ---------------------------------------------------------------------------
# guard rails
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("option,value", [
    ("search_name", "prod"),
    ("tag_filters", {"environment": ["production"]}),
    ("secret_type", 1),
    ("product_name", "cdb"),
    ("encrypt_type", 1),
    ("instance_id", "ins-abc"),
])
def test_secret_name_is_mutually_exclusive_with_list_options(monkeypatch, option, value):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", **{option: value})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]
    assert "secret_name" in exc.value.args[0]["msg"]
    assert client.calls == []


@pytest.mark.parametrize("overrides", [
    {"page_size": 0},
    {"page_size": 101},
    {"max_pages": 0},
    {"max_pages": 1001},
])
def test_page_bounds_are_enforced_before_any_call(monkeypatch, overrides):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(**overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "page_size and max_pages are outside supported bounds" in exc.value.args[0]["msg"]
    assert client.calls == []


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------

def test_list_mode_sdk_error_is_surfaced(monkeypatch):
    client = FakeSsmClient()

    def boom(request):
        raise RuntimeError("AuthFailure.SignatureExpire")

    client.ListSecrets = boom
    _wire(monkeypatch, client)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "AuthFailure.SignatureExpire" in str(payload)
    assert "secrets" not in payload


def test_exact_mode_sdk_error_is_surfaced(monkeypatch):
    client = FakeSsmClient()

    def boom(request):
        raise RuntimeError("ResourceNotFound.SecretName")

    client.DescribeSecret = boom
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "ResourceNotFound.SecretName" in str(payload)
    assert "secret" not in payload


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------

def test_exact_request_names_the_secret():
    request = mod.exact_request(FakeModels(), "prod/database")
    assert request.SecretName == "prod/database"


def test_list_request_maps_paging_order_and_filters():
    params = {"page_size": 25, "order": "ascending", "state_filter": 2,
              "search_name": "prod", "secret_type": 1, "product_name": "cdb",
              "encrypt_type": 1, "instance_id": "ins-abc",
              "tag_filters": {"environment": ["production"], "team": "database"}}
    request = mod.list_request(FakeModels(), params, 50)

    assert (request.Offset, request.Limit) == (50, 25)
    assert (request.OrderType, request.State) == (1, 2)
    assert request.SearchSecretName == "prod"
    assert request.SecretType == 1
    assert request.ProductName == "cdb"
    assert request.EncryptType == 1
    assert request.InstanceID == "ins-abc"
    # Tag filters are sorted by key and a scalar value becomes a one-item list.
    assert [(item.TagKey, item.TagValue) for item in request.TagFilters] == \
        [("environment", ["production"]), ("team", ["database"])]


def test_list_request_omits_absent_filters():
    params = {"page_size": 100, "order": "descending", "state_filter": 0,
              "search_name": None, "secret_type": None, "product_name": None,
              "encrypt_type": None, "instance_id": None, "tag_filters": {}}
    request = mod.list_request(FakeModels(), params, 0)

    assert (request.Offset, request.Limit) == (0, 100)
    assert request.OrderType == 0
    for attribute in ("SearchSecretName", "SecretType", "ProductName",
                      "EncryptType", "InstanceID", "TagFilters"):
        assert not hasattr(request, attribute)
