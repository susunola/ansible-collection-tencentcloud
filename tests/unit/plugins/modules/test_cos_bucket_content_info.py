"""Tests for the COS bucket content readers: website and policy.

This file covers the two info modules that report what a bucket serves
(``cos_bucket_website_info``) and who may read it (``cos_bucket_policy_info``).
Both are hand-written readers rather than generated ones, so each carries its
own ``normalize``/``read_*`` pair instead of going through
``module_utils/cos_bucket_read``.

The normaliser tests came first and stay as they were: they pin the two
unwrapping rules (``WebsiteConfiguration`` and the double-encoded ``Policy``).
Everything below drives ``run_module()`` end to end through the shared
harness: the real reader runs against a fake ``qcloud_cos`` client, so the
request the module makes, the bucket it addresses, the plural/singular pair it
returns, the empty and missing-bucket cases and the COS error envelope are all
observable.

COS is read through ``qcloud_cos``, not the API 3.0 SDK, so the client comes
from patching ``cos.require_cos_sdk`` (no-op) and ``cos.create_cos_client``
-- the same seam the sibling COS tests use.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_policy_info, cos_bucket_website_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
BUCKET = "public-site-1300000000"
POLICY_TEXT = '{"version":"2.0","statement":[{"action":"cos:GetObject","effect":"allow"}]}'


def test_website_normalize_unwraps_configuration():
    value = {"WebsiteConfiguration": {"IndexDocument": {"Suffix": "index.html"}}}
    assert cos_bucket_website_info.normalize(value) == value["WebsiteConfiguration"]


def test_policy_normalize_unwraps_and_decodes_policy():
    value = {"Policy": '{"version":"2.0","statement":[]}'}
    assert cos_bucket_policy_info.normalize(value) == {"version": "2.0", "statement": []}


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


WEBSITE_VALUE = {"IndexDocument": {"Suffix": "index.html"}, "ErrorDocument": {"Key": "error.html"}}
POLICY_VALUE = {"version": "2.0", "statement": [{"action": "cos:GetObject", "effect": "allow"}]}

#: module, the plural and singular return keys it documents, the normalized
#: value it yields, the raw ``qcloud_cos`` response that produces it, the
#: client method the module must call and the extra module arguments beyond
#: ``name``/``appid``.
CASES = (
    (
        cos_bucket_website_info, "websites", "website",
        WEBSITE_VALUE, {"WebsiteConfiguration": WEBSITE_VALUE},
        "get_bucket_website", {},
    ),
    (
        cos_bucket_policy_info, "policies", "policy",
        POLICY_VALUE, {"Policy": POLICY_TEXT},
        "get_bucket_policy", {},
    ),
)

#: Ids keep the parametrised runs readable in the pytest output.
IDS = [case[0].__name__ for case in CASES]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_returns_the_value_twice(monkeypatch, module, plural, singular, value, response, reader, extra):
    """The reader returns the normalized value under both documented keys."""
    client = FakeCosClient(response)
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID, **extra)

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
    module_args(name="public-site", appid=APPID, **extra)

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
    module_args(name="public-site", **extra)

    run(module.run_module)

    assert client.buckets == [BUCKET]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_returns_empty_keys_without_a_configuration(monkeypatch, module, plural, singular, value, response, reader, extra):
    """An empty provider response is an empty list and a null value.

    RED for ``cos_bucket_policy_info``: it reports ``policies: []`` next to
    ``policy: {}``. It documents "empty or single-element list" and
    "effective normalized bucket policy or null", and it builds that pair from
    one value with ``[value] if value else []``, which can only agree when the
    value is ``None``. ``normalize`` opens with ``if value is None``, so an
    empty (but present) ``GetBucketPolicy`` mapping passes straight through.

    The fix belongs in ``normalize`` (``if not value: return None``), not in
    this assertion, so the test stays red until the module is corrected; the
    website reader asserted here covers the same contract and passes.
    """
    client = FakeCosClient({})
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID, **extra)

    payload = run(module.run_module)

    assert payload == {"changed": False, plural: [], singular: None}
    assert client.buckets == [BUCKET]


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_treats_a_missing_bucket_as_an_empty_result(monkeypatch, module, plural, singular, value, response, reader, extra):
    """``NoSuchBucket`` is "nothing configured", not a failure."""
    client = FakeCosClient(error=FakeCosServiceError(
        "bucket not found", code="NoSuchBucket", status=404))
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID, **extra)

    payload = run(module.run_module)

    assert payload[plural] == []
    assert payload[singular] is None
    assert payload["changed"] is False


@pytest.mark.parametrize("module,plural,singular,value,response,reader,extra", CASES, ids=IDS)
def test_run_module_maps_a_cos_error_to_fail_json(monkeypatch, module, plural, singular, value, response, reader, extra):
    """Any other COS error becomes the module's failure envelope."""
    client = FakeCosClient(error=FakeCosServiceError("no permission to read the bucket"))
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID, **extra)

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
    module_args(name="public-site", appid=APPID, _ansible_check_mode=True, **extra)

    payload = run(module.run_module)

    assert payload[singular] == value
    assert client.buckets == [BUCKET]


def test_policy_normalize_decodes_a_json_string_response(monkeypatch):
    """COS may return the policy JSON-encoded; the module hands back a mapping."""
    client = FakeCosClient(POLICY_TEXT)
    _patch_cos_client(monkeypatch, client)
    module_args(name="application-data", appid=APPID)

    payload = run(cos_bucket_policy_info.run_module)

    assert payload["policy"] == POLICY_VALUE
    assert payload["policies"] == [POLICY_VALUE]


def test_policy_normalize_returns_none_for_a_null_policy(monkeypatch):
    client = FakeCosClient({"Policy": None})
    _patch_cos_client(monkeypatch, client)
    module_args(name="application-data", appid=APPID)

    payload = run(cos_bucket_policy_info.run_module)

    assert payload == {"changed": False, "policies": [], "policy": None}


def test_website_normalize_returns_none_for_a_null_configuration(monkeypatch):
    """An explicit null ``WebsiteConfiguration`` takes the empty path."""
    client = FakeCosClient({"WebsiteConfiguration": None})
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID)

    payload = run(cos_bucket_website_info.run_module)

    assert payload == {"changed": False, "websites": [], "website": None}


def test_website_empty_configuration_reports_no_website(monkeypatch):
    """``{"WebsiteConfiguration": {}}`` means "not configured" -- RED TEST.

    ``cos_bucket_website_info.normalize`` turns the falsy *response* into
    ``None`` but unwraps the key first, so an empty mapping under
    ``WebsiteConfiguration`` survives: the singular key is ``{}`` while the
    plural key is ``[]``, and the documented pair disagrees with itself.

    The fix belongs in ``normalize`` (``if not value: return None``), not in
    this assertion, so the test stays red until the module is corrected.
    """
    client = FakeCosClient({"WebsiteConfiguration": {}})
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID)

    payload = run(cos_bucket_website_info.run_module)

    assert payload == {"changed": False, "websites": [], "website": None}
