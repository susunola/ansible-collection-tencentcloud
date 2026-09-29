"""Tests for the COS bucket retention readers: object lock and origin.

This file covers the two info modules that report how long a bucket's objects
are protected (``cos_bucket_object_lock_info``) and where a bucket's requests
are pulled from (``cos_bucket_origin_info``). Both read through the shared
``module_utils/cos_bucket_read`` helpers, so the normalisers they expose are
covered first and the readers afterwards.

The normaliser tests came first and stay as they were: they pin the two
coercions the helpers promise (``Years`` as an int, origin rules ordered by
``RulePriority``). Everything below drives ``run_module()`` end to end through
the shared harness, letting the real ``get_object_lock``/``get_origin``
helpers run against a fake ``qcloud_cos`` client. That is what makes the
request observable -- including the ``Id="default"``-style reader arguments
and the bucket the module addresses.

COS is read through ``qcloud_cos``, not the API 3.0 SDK, so the client comes
from patching ``cos.require_cos_sdk`` (no-op) and ``cos.create_cos_client``
-- the same seam the sibling COS tests use.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_object_lock as normalize_lock
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_object_lock_info, cos_bucket_origin_info
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_origin import normalize as normalize_origin
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
BUCKET = "archive-1300000000"


def test_object_lock_normalize_converts_retention_period():
    value = {"ObjectLockEnabled": "Enabled", "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Years": "7"}}}
    assert normalize_lock(value)["Rule"]["DefaultRetention"]["Years"] == 7


def test_origin_normalize_sorts_rules_by_priority():
    value = {"OriginRule": [{"RulePriority": "2"}, {"RulePriority": "1"}]}
    assert [item["RulePriority"] for item in normalize_origin(value)["OriginRule"]] == ["1", "2"]


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


LOCK_VALUE = {
    "ObjectLockEnabled": "Enabled",
    "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 30}},
}
ORIGIN_VALUE = {
    "OriginRule": [
        {"RulePriority": "1", "OriginType": "OriginTypeCrawler", "OriginParameter": "crawler.example"},
        {"RulePriority": "2", "OriginType": "OriginTypeHeader", "OriginParameter": "X-Forwarded-Host"},
    ]
}

#: module, the plural and singular return keys it documents, the normalized
#: value it yields, the raw ``qcloud_cos`` response that produces it, the
#: client method the module must call and the extra module arguments beyond
#: ``name``/``appid``.
CASES = (
    (
        cos_bucket_object_lock_info, "object_locks", "object_lock",
        LOCK_VALUE, {"ObjectLockConfiguration": LOCK_VALUE},
        "get_bucket_object_lock", {},
    ),
    (
        cos_bucket_origin_info, "origins", "origin",
        ORIGIN_VALUE, {"OriginConfiguration": ORIGIN_VALUE},
        "get_bucket_origin", {},
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

    assert client.calls == [(reader, {"Bucket": BUCKET})]


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
def test_run_module_returns_empty_keys_without_a_configuration(monkeypatch, module, plural, singular, value, response, reader, extra):
    """An empty provider response is an empty list and a null value."""
    client = FakeCosClient({})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, **extra)

    payload = run(module.run_module)

    assert payload == {"changed": False, plural: [], singular: None}
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
    client = FakeCosClient(error=FakeCosServiceError(
        "not found", code=None, status=404))
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


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_reads_in_check_mode(monkeypatch, module, plural, singular, value, response, reader, extra):
    """A reader can run in check mode: it only ever reads."""
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID, _ansible_check_mode=True, **extra)

    payload = run(module.run_module)

    assert payload[singular] == value
    assert client.buckets == [BUCKET]


def test_object_lock_reader_asks_for_the_default_configuration(monkeypatch):
    """The object-lock reader takes no rule id: COS has one per bucket."""
    client = FakeCosClient({"ObjectLockConfiguration": LOCK_VALUE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_object_lock_info.run_module)

    assert payload["object_lock"] == LOCK_VALUE
    assert client.calls == [("get_bucket_object_lock", {"Bucket": BUCKET})]


def test_origin_normalize_numbers_priorities_for_ordering(monkeypatch):
    """Rules arrive unsorted and come back in ``RulePriority`` order.

    ``normalize_origin`` sorts on ``int(RulePriority)``, so "10" must not sort
    before "2" the way a plain string sort would.
    """
    response = {"OriginConfiguration": {"OriginRule": [
        {"RulePriority": "10", "OriginType": "OriginTypeHeader", "OriginParameter": "X-Ten"},
        {"RulePriority": "2", "OriginType": "OriginTypeCrawler", "OriginParameter": "crawler.example"},
    ]}}
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_origin_info.run_module)

    assert [rule["RulePriority"] for rule in payload["origin"]["OriginRule"]] == ["2", "10"]


def test_origin_normalize_wraps_a_single_rule_returned_as_a_mapping(monkeypatch):
    """COS omits the list wrapper when a bucket has exactly one origin rule."""
    response = {"OriginConfiguration": {"OriginRule": {
        "RulePriority": "1", "OriginType": "OriginTypeCrawler", "OriginParameter": "crawler.example",
    }}}
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_origin_info.run_module)

    assert payload["origin"]["OriginRule"] == [{
        "RulePriority": "1", "OriginType": "OriginTypeCrawler", "OriginParameter": "crawler.example",
    }]


def test_object_lock_normalize_omits_an_absent_retention_rule(monkeypatch):
    """A bucket with object lock on but no default retention keeps no rule."""
    client = FakeCosClient({"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_object_lock_info.run_module)

    assert payload["object_lock"] == {"ObjectLockEnabled": "Enabled"}
    assert "Rule" not in payload["object_lock"]
