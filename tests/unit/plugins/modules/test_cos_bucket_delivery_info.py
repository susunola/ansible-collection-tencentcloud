"""Tests for the COS bucket delivery readers: inventory, replication, control.

This file covers the three info modules that describe how a bucket hands its
data to somewhere else: its inventory reports (``cos_bucket_inventory_info``),
its cross-region replication rules (``cos_bucket_replication_info``) and the
response headers it rewrites (``cos_bucket_response_control_info``). All three
read through ``module_utils/cos_bucket_read``, so the normalisers they expose
are covered first and the ``run_module()`` flows afterwards.

The normaliser tests came first and stay as they were: they pin the three
coercions the helpers promise (the inventory rule id, the optional-field
ordering and the replication rule ordering). Everything below drives
``run_module()`` end to end through the shared harness, letting the real
``get_inventory``/``get_replication``/``get_control`` helpers run against a
fake ``qcloud_cos`` client. The inventory reader takes an extra ``Id``
argument, so the request it builds is asserted in full.

COS is read through ``qcloud_cos``, not the API 3.0 SDK, so the client comes
from patching ``cos.require_cos_sdk`` (no-op) and ``cos.create_cos_client``
-- the same seam the sibling COS tests use.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import (
    cos_bucket_inventory_info,
    cos_bucket_replication_info,
    cos_bucket_response_control_info,
)
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_inventory import normalize as normalize_inventory
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_replication import normalize as normalize_replication
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_response_control import normalize as normalize_control
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
BUCKET = "archive-1300000000"
INVENTORY_ID = "daily-objects"


def test_replication_normalize_sorts_rules():
    value = {"Role": "role", "Rule": [{"ID": "b"}, {"ID": "a"}]}
    assert [x["ID"] for x in normalize_replication(value)["Rule"]] == ["a", "b"]


def test_response_control_normalize_sorts_parameters():
    value = {"ControlParamList": {"Param": ["response-expires", "response-content-type"]}}
    assert normalize_control(value)["ControlParamList"]["Param"] == ["response-content-type", "response-expires"]


def test_inventory_normalize_sets_id_and_sorts_optional_fields():
    value = {"OptionalFields": {"Field": ["Size", "ETag"]}}
    normalized = normalize_inventory(value, "daily")
    assert normalized["Id"] == "daily"
    assert normalized["OptionalFields"]["Field"] == ["ETag", "Size"]


class FakeCosServiceError(Exception):
    """Stand-in for the ``qcloud_cos`` ``CosServiceError``.

    ``cos.is_not_found`` reaches for ``get_error_code``/``get_status_code``
    and ``cos.fail_on_cos_error`` also reads ``get_request_id``, so the fake
    has to answer all three the way the real exception does.
    """

    def __init__(self, message, code="AccessDenied", status=403, request_id="req-cos"):
        super(FakeCosServiceError, self).__init__(message)
        self._code = code
        self._status = status
        self._request_id = request_id

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status

    def get_request_id(self):
        return self._request_id


class FakeCosClient(object):
    """COS client answering every ``get_bucket_*`` read with one canned result.

    The readers call an arbitrary ``client.get_bucket_<thing>(Bucket=...)``
    method, so the client resolves any such attribute to a recorder: each call
    appends ``(method, kwargs)`` to :attr:`calls`, then returns
    :attr:`response` or raises :attr:`error`.
    """

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def read(**kwargs):
            self.calls.append((name, kwargs))
            if self.error is not None:
                raise self.error
            return self.response

        return read

    @property
    def buckets(self):
        """The bucket each recorded request addressed, in call order."""
        return [kwargs.get("Bucket") for _method, kwargs in self.calls]


def _patch_cos_client(monkeypatch, client):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: client)


INVENTORY_RESPONSE = {
    "Id": "ignored-by-the-module",
    "IsEnabled": "true",
    "Filter": {"Prefix": "logs/"},
    "OptionalFields": {"Field": ["Size", "ETag"]},
    "Schedule": {"Frequency": "Daily"},
    "Destination": {"Bucket": "dest-1300000000", "Format": "CSV"},
}
INVENTORY_VALUE = dict(INVENTORY_RESPONSE, Id=INVENTORY_ID, OptionalFields={"Field": ["ETag", "Size"]})
REPLICATION_VALUE = {
    "Role": "qcs::cam::uin/100000000001:uin/100000000001",
    "Rule": [
        {"ID": "rule-a", "Prefix": "a/", "Status": "Enabled", "Destination": {"Bucket": "dest-1300000000"}},
        {"ID": "rule-b", "Prefix": "b/", "Status": "Enabled", "Destination": {"Bucket": "dest-1300000000"}},
    ],
}
CONTROL_VALUE = {"ControlParamList": {"Param": ["response-content-type", "response-expires"]}}

#: module, the plural and singular return keys it documents, the normalized
#: value it yields, the raw ``qcloud_cos`` response that produces it, the
#: client method the module must call and the extra module arguments beyond
#: ``name``/``appid``.
CASES = (
    (
        cos_bucket_inventory_info, "inventories", "inventory",
        INVENTORY_VALUE, {"InventoryConfiguration": INVENTORY_RESPONSE},
        "get_bucket_inventory", {"inventory_id": INVENTORY_ID},
    ),
    (
        cos_bucket_replication_info, "replications", "replication",
        REPLICATION_VALUE, {"ReplicationConfiguration": REPLICATION_VALUE},
        "get_bucket_replication", {},
    ),
    (
        cos_bucket_response_control_info, "response_controls", "response_control",
        CONTROL_VALUE, {"ResponseControlConfiguration": CONTROL_VALUE},
        "get_bucket_response_control", {},
    ),
)

#: Ids keep the parametrised runs readable in the pytest output.
IDS = [case[0].__name__ for case in CASES]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_returns_the_value_twice(monkeypatch, module, plural, singular, value, response, reader, extra):
    """The shared reader returns the normalized value under both keys."""
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, **extra)

    payload = run(module.run_module)

    assert payload["changed"] is False
    assert payload[plural] == [value]
    assert payload[singular] == value
    assert payload.keys() == {"changed", plural, singular}


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_addresses_the_bucket_with_its_appid(monkeypatch, module, plural, singular, value, response, reader, extra):
    """A short ``name`` is suffixed with the appid before the read."""
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, **extra)

    run(module.run_module)

    assert client.buckets == [BUCKET]


def test_inventory_reader_forwards_the_rule_id(monkeypatch):
    """``GetBucketInventory`` needs the rule id, not just the bucket."""
    client = FakeCosClient({"InventoryConfiguration": INVENTORY_RESPONSE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, inventory_id=INVENTORY_ID)

    payload = run(cos_bucket_inventory_info.run_module)

    assert client.calls == [("get_bucket_inventory", {"Bucket": BUCKET, "Id": INVENTORY_ID})]
    assert payload["inventory"]["Id"] == INVENTORY_ID


def test_replication_reader_takes_no_extra_reader_argument(monkeypatch):
    """``GetBucketReplication`` addresses the bucket and nothing else."""
    client = FakeCosClient({"ReplicationConfiguration": REPLICATION_VALUE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    run(cos_bucket_replication_info.run_module)

    assert client.calls == [("get_bucket_replication", {"Bucket": BUCKET})]


def test_response_control_reader_takes_no_extra_reader_argument(monkeypatch):
    """``GetBucketResponseControl`` addresses the bucket and nothing else."""
    client = FakeCosClient({"ResponseControlConfiguration": CONTROL_VALUE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    run(cos_bucket_response_control_info.run_module)

    assert client.calls == [("get_bucket_response_control", {"Bucket": BUCKET})]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_does_not_suffix_an_already_full_bucket_name(monkeypatch, module, plural, singular, value, response, reader, extra):
    """A full ``<name>-<appid>`` name is addressable as-is.

    ``cos.bucket_full_name`` is idempotent, so a name that ``cos_bucket_info``
    returned can be fed straight back in.
    """
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name=BUCKET, appid=APPID, **extra)

    run(module.run_module)

    assert client.buckets == [BUCKET]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_resolves_the_appid_when_it_is_not_given(monkeypatch, module, plural, singular, value, response, reader, extra):
    """``appid`` is optional: it is resolved through CAM instead.

    ``cos.resolve_appid`` falls back to ``fetch_appid`` when the parameter is
    absent, so the test patches that fallback rather than passing ``appid``.
    """
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    monkeypatch.setattr(cos, "fetch_appid", lambda module: APPID)
    module_args(name="archive", **extra)

    run(module.run_module)

    assert client.buckets == [BUCKET]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_treats_a_missing_bucket_as_an_empty_result(monkeypatch, module, plural, singular, value, response, reader, extra):
    """``NoSuchBucket`` is "nothing configured", not a failure.

    ``cos_bucket_read._read`` swallows the exception when
    ``cos.is_not_found`` recognises it; everything else propagates.
    """
    client = FakeCosClient(error=FakeCosServiceError(
        "bucket not found", code="NoSuchBucket", status=404))
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, **extra)

    payload = run(module.run_module)

    assert payload[plural] == []
    assert payload[singular] is None
    assert payload["changed"] is False


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_treats_a_404_as_an_empty_result(monkeypatch, module, plural, singular, value, response, reader, extra):
    """A bare 404 counts as absent even without a COS error code."""
    client = FakeCosClient(error=FakeCosServiceError("not found", code=None, status=404))
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, **extra)

    payload = run(module.run_module)

    assert payload[plural] == []
    assert payload[singular] is None


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_maps_a_cos_error_to_fail_json(monkeypatch, module, plural, singular, value, response, reader, extra):
    """Any other COS error becomes the module's failure envelope."""
    client = FakeCosClient(error=FakeCosServiceError("no permission to read the bucket"))
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, **extra)

    with pytest.raises(AnsibleFailJson) as failure:
        run(module.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert payload["error"] == "no permission to read the bucket"
    assert payload["error_code"] == "AccessDenied"
    assert payload["request_id"] == "req-cos"
    assert client.buckets == [BUCKET]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_requires_the_bucket_name(monkeypatch, module, plural, singular, value, response, reader, extra):
    _patch_cos_client(monkeypatch, FakeCosClient(response))
    module_args(appid=APPID, **extra)

    with pytest.raises(AnsibleFailJson) as failure:
        run(module.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: name"


def test_inventory_reader_requires_the_rule_id(monkeypatch):
    """Unlike its siblings, the inventory reader cannot run without an id."""
    _patch_cos_client(monkeypatch, FakeCosClient({"InventoryConfiguration": INVENTORY_RESPONSE}))
    module_args(name="archive", appid=APPID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(cos_bucket_inventory_info.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: inventory_id"


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_reads_in_check_mode(monkeypatch, module, plural, singular, value, response, reader, extra):
    """A reader can run in check mode: it only ever reads."""
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, _ansible_check_mode=True, **extra)

    payload = run(module.run_module)

    assert payload[singular] == value
    assert client.buckets == [BUCKET]


def test_inventory_value_wins_over_the_provider_id(monkeypatch):
    """The requested rule id is authoritative, not the echoed ``Id``."""
    client = FakeCosClient({"InventoryConfiguration": INVENTORY_RESPONSE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, inventory_id="weekly-audit")

    payload = run(cos_bucket_inventory_info.run_module)

    assert payload["inventory"]["Id"] == "weekly-audit"
    assert payload["inventory"]["OptionalFields"]["Field"] == ["ETag", "Size"]


def test_inventory_normalize_tolerates_a_null_optional_field_list(monkeypatch):
    """``OptionalFields: null`` means "no optional fields", not a crash."""
    response = {"InventoryConfiguration": {"IsEnabled": "true", "OptionalFields": None,
                                           "Destination": {"Bucket": "dest-1300000000"}}}
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, inventory_id=INVENTORY_ID)

    payload = run(cos_bucket_inventory_info.run_module)

    assert payload["inventory"]["OptionalFields"] is None
    assert payload["inventories"] == [payload["inventory"]]


def test_replication_orders_rules_by_id_then_prefix(monkeypatch):
    """Rules sorted on ``(ID, Prefix)``, not on the raw provider order."""
    response = {"ReplicationConfiguration": {"Role": "role", "Rule": [
        {"ID": "rule-b", "Prefix": "a/"},
        {"ID": "rule-a", "Prefix": "z/"},
        {"ID": "rule-a", "Prefix": "a/"},
    ]}}
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_replication_info.run_module)

    assert [(rule["ID"], rule["Prefix"]) for rule in payload["replication"]["Rule"]] == [
        ("rule-a", "a/"), ("rule-a", "z/"), ("rule-b", "a/"),
    ]


def test_response_control_accepts_a_bare_parameter_string(monkeypatch):
    """COS returns a bare string when a bucket rewrites one header."""
    response = {"ResponseControlConfiguration": {"ControlParamList": {"Param": "response-expires"}}}
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_response_control_info.run_module)

    assert payload["response_control"] == {"ControlParamList": {"Param": ["response-expires"]}}
    assert payload["response_controls"] == [payload["response_control"]]


def test_response_control_empty_configuration_reports_no_control(monkeypatch):
    """An envelope with no parameters means "nothing rewritten" -- RED TEST.

    ``normalize_control`` always returns
    ``{"ControlParamList": {"Param": [...]}}``, which is truthy even when the
    list is empty, so the module reports ``response_control`` as that empty
    envelope instead of ``null``. The documented pair then disagrees with
    itself: ``response_controls`` is non-empty while ``response_control`` is
    falsy. Sibling readers that unwrap a nested list (``normalize_object_lock``
    returning ``None`` for an empty mapping) do not have this problem.

    The fix belongs in ``normalize_control`` (return ``None`` when there are
    no parameters), not in this assertion, so the test stays red until the
    module is corrected.
    """
    client = FakeCosClient({"ResponseControlConfiguration": {}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_response_control_info.run_module)

    assert payload == {"changed": False, "response_controls": [], "response_control": None}
