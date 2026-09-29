"""Tests for the COS bucket access readers: referer and intelligent tiering.

This file covers the two info modules that describe who may link to a bucket
(``cos_bucket_referer_info``) and how its objects migrate between storage
classes (``cos_bucket_intelligent_tiering_info``). The referer reader is
hand-written with its own ``normalize``, while the tiering reader goes through
``module_utils/cos_bucket_read.get_rule`` and asks for the ``default`` rule by
id.

The normaliser tests came first and stay as they were: they pin the two
coercions the readers promise (a disabled referer is no configuration, and the
tiering day/request counters are ints). Everything below drives
``run_module()`` end to end through the shared harness, so the request, the
bucket, the plural/singular pair, the empty and missing-bucket cases and the
COS error envelope are all observable.

COS is read through ``qcloud_cos``, not the API 3.0 SDK, so the client comes
from patching ``cos.require_cos_sdk`` (no-op) and ``cos.create_cos_client``
-- the same seam the sibling COS tests use.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_tiering
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_intelligent_tiering_info, cos_bucket_referer_info
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_referer import normalize as normalize_referer
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
BUCKET = "archive-1300000000"


def test_referer_normalize_sorts_domains_and_handles_disabled():
    assert normalize_referer({"Status": "Disabled"}) is None
    value = {"Status": "Enabled", "RefererType": "White-List", "EmptyReferConfiguration": "Deny", "DomainList": {"Domain": ["b.example", "a.example"]}}
    assert normalize_referer(value)["DomainList"]["Domain"] == ["a.example", "b.example"]


def test_intelligent_tiering_normalize_converts_numeric_fields():
    value = {"Id": "default", "Status": "Enabled", "Tiering": {"AccessTier": "INFREQUENT", "Days": "30", "RequestFrequent": "1"}}
    assert normalize_tiering(value)["Tiering"] == {"AccessTier": "INFREQUENT", "Days": 30, "RequestFrequent": 1}


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


REFERER_VALUE = {
    "Status": "Enabled",
    "RefererType": "White-List",
    "EmptyReferConfiguration": "Deny",
    "DomainList": {"Domain": ["*.example.com", "app.example.com"]},
}
TIERING_VALUE = {
    "Id": "default",
    "Status": "Enabled",
    "Tiering": {"AccessTier": "INFREQUENT", "Days": 30, "RequestFrequent": 1},
}

#: module, the plural and singular return keys it documents, the normalized
#: value it yields, the raw ``qcloud_cos`` response that produces it, the
#: client method the module must call and the extra module arguments beyond
#: ``name``/``appid``.
CASES = (
    (
        cos_bucket_referer_info, "referers", "referer",
        REFERER_VALUE, REFERER_VALUE,
        "get_bucket_referer", {},
    ),
    (
        cos_bucket_intelligent_tiering_info, "intelligent_tiering_rules", "intelligent_tiering",
        TIERING_VALUE, {"IntelligentTieringConfiguration": TIERING_VALUE},
        "get_bucket_intelligenttiering_v2", {},
    ),
)

#: Ids keep the parametrised runs readable in the pytest output.
IDS = [case[0].__name__ for case in CASES]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_returns_the_value_twice(monkeypatch, module, plural, singular, value, response, reader, extra):
    """The reader returns the normalized value under both documented keys."""
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


def test_tiering_reader_asks_for_the_default_rule(monkeypatch):
    """COS keeps one intelligent-tiering rule per bucket, under ``default``."""
    client = FakeCosClient({"IntelligentTieringConfiguration": TIERING_VALUE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_intelligent_tiering_info.run_module)

    assert client.calls == [("get_bucket_intelligenttiering_v2", {"Bucket": BUCKET, "Id": "default"})]
    assert payload["intelligent_tiering"] == TIERING_VALUE


def test_referer_reader_takes_no_extra_reader_argument(monkeypatch):
    """``GetBucketReferer`` addresses the bucket and nothing else."""
    client = FakeCosClient(REFERER_VALUE)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    run(cos_bucket_referer_info.run_module)

    assert client.calls == [("get_bucket_referer", {"Bucket": BUCKET})]


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


def test_referer_disabled_reports_empty_keys(monkeypatch):
    """A referer list that is switched off is no configuration at all."""
    client = FakeCosClient({"Status": "Disabled"})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_referer_info.run_module)

    assert payload == {"changed": False, "referers": [], "referer": None}
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


def test_referer_single_domain_string_is_normalized_to_a_list(monkeypatch):
    """COS returns a bare string when a rule holds exactly one domain."""
    response = {
        "Status": "Enabled", "RefererType": "Black-List", "EmptyReferConfiguration": "Allow",
        "DomainList": {"Domain": "*.example.com"},
    }
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_referer_info.run_module)

    assert payload["referer"]["DomainList"]["Domain"] == ["*.example.com"]
    assert payload["referers"] == [payload["referer"]]


def test_tiering_normalize_defaults_an_absent_rule_id(monkeypatch):
    """COS omits ``Id`` for the bucket's single rule; the module names it."""
    client = FakeCosClient({"IntelligentTieringConfiguration": {
        "Status": "Enabled",
        "Tiering": {"AccessTier": "INFREQUENT", "Days": "30", "RequestFrequent": "1"},
    }})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_intelligent_tiering_info.run_module)

    assert payload["intelligent_tiering"] == TIERING_VALUE


def test_tiering_normalize_reports_a_rule_whose_counters_are_zero(monkeypatch):
    """A tiering rule with no request frequency is valid, not a crash -- RED TEST.

    ``normalize_tiering`` reads ``int(tiering["Days"])`` and
    ``int(tiering["RequestFrequent"])`` rather than using ``.get``, so a
    response that omits a counter -- the expected shape for a zero value, and
    the only shape an empty ``Tiering`` mapping can produce -- raises
    ``KeyError``. ``read_rule`` does not catch it (it only recognises
    not-found errors), so the module reports a COS request failure whose
    ``error`` is a bare ``"'Days'"`` for a bucket that is merely unconfigured.
    Its sibling normaliser ``normalize_object_lock`` guards the same two
    fields with ``is not None`` checks, so the pattern exists in this module
    family already.

    The fix belongs in ``normalize_tiering`` (use ``.get`` and treat a missing
    counter as zero, and return ``None`` for an empty configuration), not in
    this assertion, so the test stays red until the module is corrected.
    """
    client = FakeCosClient({"IntelligentTieringConfiguration": {}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_intelligent_tiering_info.run_module)

    assert payload == {
        "changed": False, "intelligent_tiering_rules": [], "intelligent_tiering": None,
    }
