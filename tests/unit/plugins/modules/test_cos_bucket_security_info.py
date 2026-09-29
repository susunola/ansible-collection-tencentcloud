"""Tests for the COS bucket security readers: encryption and logging.

This file covers the two info modules that describe how a bucket's data is
protected at rest (``cos_bucket_encryption_info``) and where its access logs
go (``cos_bucket_logging_info``). Both are hand-written readers with their own
``normalize``/``read_*`` pair, so the normalisers are covered first and the
``run_module()`` flows afterwards.

The normaliser tests came first and stay as they were: they pin the
``ServerSideEncryptionConfiguration`` unwrap and the "logging disabled means
no configuration" rule. Everything below drives ``run_module()`` end to end
through the shared harness, so the real reader runs against a fake
``qcloud_cos`` client and the request, the bucket, the plural/singular pair,
the empty and missing-bucket cases and the COS error envelope are all
observable.

COS is read through ``qcloud_cos``, not the API 3.0 SDK, so the client comes
from patching ``cos.require_cos_sdk`` (no-op) and ``cos.create_cos_client``
-- the same seam the sibling COS tests use.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_encryption_info, cos_bucket_logging_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
BUCKET = "archive-1300000000"


def test_encryption_normalize_extracts_rules():
    value = {"ServerSideEncryptionConfiguration": {"Rule": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}}
    assert cos_bucket_encryption_info.normalize(value) == value["ServerSideEncryptionConfiguration"]


def test_logging_normalize_handles_disabled_and_defaults_prefix():
    assert cos_bucket_logging_info.normalize({"BucketLoggingStatus": {}}) is None
    value = {"BucketLoggingStatus": {"LoggingEnabled": {"TargetBucket": "logs-1250000000"}}}
    assert cos_bucket_logging_info.normalize(value) == {"LoggingEnabled": {"TargetBucket": "logs-1250000000", "TargetPrefix": ""}}


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


ENCRYPTION_RULE = {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
ENCRYPTION_VALUE = {"Rule": [ENCRYPTION_RULE]}
LOGGING_VALUE = {"LoggingEnabled": {"TargetBucket": "logs-1300000000", "TargetPrefix": "access/"}}

#: module, the plural and singular return keys it documents, the normalized
#: value it yields, the raw ``qcloud_cos`` response that produces it, the
#: client method the module must call and the extra module arguments beyond
#: ``name``/``appid``.
CASES = (
    (
        cos_bucket_encryption_info, "encryptions", "encryption",
        ENCRYPTION_VALUE, {"ServerSideEncryptionConfiguration": ENCRYPTION_VALUE},
        "get_bucket_encryption", {},
    ),
    (
        cos_bucket_logging_info, "logging_configurations", "logging",
        LOGGING_VALUE, {"BucketLoggingStatus": LOGGING_VALUE},
        "get_bucket_logging", {},
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


def test_logging_disabled_reports_empty_keys(monkeypatch):
    """A logging-disabled bucket reports an empty list and a null value.

    ``BucketLoggingStatus`` carrying no ``LoggingEnabled`` is the provider's
    way of saying logging is off, and ``normalize`` maps it to ``None``.
    """
    client = FakeCosClient({"BucketLoggingStatus": {}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_logging_info.run_module)

    assert payload == {"changed": False, "logging_configurations": [], "logging": None}
    assert client.buckets == [BUCKET]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_treats_a_missing_bucket_as_an_empty_result(monkeypatch, module, plural, singular, value, response, reader, extra):
    """``NoSuchBucket`` is "nothing configured", not a failure."""
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


def test_logging_normalize_defaults_an_absent_target_prefix(monkeypatch):
    """COS omits ``TargetPrefix`` when the bucket logs to its root."""
    response = {"BucketLoggingStatus": {"LoggingEnabled": {"TargetBucket": "logs-1300000000"}}}
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_logging_info.run_module)

    assert payload["logging"]["LoggingEnabled"]["TargetPrefix"] == ""
    assert payload["logging_configurations"] == [payload["logging"]]


def test_logging_normalize_keeps_a_configured_target_prefix(monkeypatch):
    client = FakeCosClient({"BucketLoggingStatus": LOGGING_VALUE})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_logging_info.run_module)

    assert payload["logging"]["LoggingEnabled"] == {
        "TargetBucket": "logs-1300000000", "TargetPrefix": "access/",
    }


def test_encryption_normalize_accepts_the_unwrapped_configuration(monkeypatch):
    """Some SDK paths hand back the configuration without its envelope."""
    client = FakeCosClient(ENCRYPTION_VALUE)
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_encryption_info.run_module)

    assert payload["encryption"] == ENCRYPTION_VALUE


def test_encryption_normalize_keeps_every_rule(monkeypatch):
    """A bucket may carry more than one SSE rule; none may be dropped."""
    rules = [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}},
             {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "KMS", "KMSMasterKeyID": "key-1"}}]
    client = FakeCosClient({"ServerSideEncryptionConfiguration": {"Rule": rules}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_encryption_info.run_module)

    assert payload["encryption"] == {"Rule": rules}


def test_encryption_empty_configuration_reports_no_encryption(monkeypatch):
    """An SSE envelope with no rules means "SSE is not configured" -- RED TEST.

    ``cos_bucket_encryption_info.normalize`` unwraps the envelope with
    ``value.get("ServerSideEncryptionConfiguration", value)`` and returns
    ``{"Rule": root.get("Rule") or []}``, which is a truthy dict even when the
    bucket has no rules at all. The module then reports ``encryption`` as that
    empty envelope rather than ``null``, so a caller cannot tell "SSE off"
    (``{}``-shaped) from "SSE on" using the documented singular key.

    The fix belongs in ``normalize`` (return ``None`` when the rule list is
    empty), not in this assertion, so the test stays red until the module is
    corrected.
    """
    client = FakeCosClient({"ServerSideEncryptionConfiguration": {}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="archive", appid=APPID)

    payload = run(cos_bucket_encryption_info.run_module)

    assert payload == {"changed": False, "encryptions": [], "encryption": None}
