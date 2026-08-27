"""Unit tests for the COS (qcloud_cos) module_utils helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404, request_id="req-fake"):
        super(FakeCosError, self).__init__(code)
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
    """In-memory stand-in for CosS3Client covering the read paths."""

    def __init__(self, buckets=None):
        # full_name -> {"location", "acl", "versioning", "tags"}
        self.buckets = dict(buckets or {})

    def head_bucket(self, Bucket, **kwargs):
        if Bucket not in self.buckets:
            raise FakeCosError("NoSuchBucket")
        return {}

    def get_bucket_location(self, Bucket, **kwargs):
        return {"LocationConstraint": self.buckets[Bucket]["location"]}

    def get_bucket_acl(self, Bucket, **kwargs):
        return {"CannedACL": self.buckets[Bucket]["acl"], "AccessControlList": {"Grant": []}}

    def get_bucket_versioning(self, Bucket, **kwargs):
        status = self.buckets[Bucket].get("versioning")
        return {"Status": status} if status else {}

    def get_bucket_tagging(self, Bucket, **kwargs):
        tags = self.buckets[Bucket].get("tags") or {}
        if not tags:
            raise FakeCosError("NoSuchTagSet")
        return {"TagSet": {"Tag": [{"Key": k, "Value": v} for k, v in sorted(tags.items())]}}

    def list_buckets(self, **kwargs):
        return {
            "Buckets": {
                "Bucket": [
                    {"Name": name, "Location": data["location"], "CreationDate": "2026-08-26T00:00:00Z"}
                    for name, data in sorted(self.buckets.items())
                ]
            }
        }


def _bucket(location="ap-guangzhou", acl="private", versioning=None, tags=None):
    return {"location": location, "acl": acl, "versioning": versioning, "tags": tags or {}}


def test_error_accessors():
    exc = FakeCosError("NoSuchBucket", status=404, request_id="req-1")
    assert cos.error_code(exc) == "NoSuchBucket"
    assert cos.status_code(exc) == 404
    assert cos.request_id(exc) == "req-1"
    assert cos.error_code(ValueError("boom")) is None
    assert cos.request_id(ValueError("boom")) is None


def test_is_not_found_codes_and_status():
    assert cos.is_not_found(FakeCosError("NoSuchBucket"))
    assert cos.is_not_found(FakeCosError("NoSuchTagSet"))
    assert cos.is_not_found(FakeCosError("AnythingElse", status=404))
    assert not cos.is_not_found(FakeCosError("AccessDenied", status=403))
    assert not cos.is_not_found(ValueError("boom"))


def test_is_idempotent_success_matches_not_found():
    assert cos.is_idempotent_success(FakeCosError("NoSuchBucket"))
    assert not cos.is_idempotent_success(FakeCosError("BucketNotEmpty", status=409))


def test_bucket_full_name_appends_appid():
    assert cos.bucket_full_name("mybucket", "1300000000") == "mybucket-1300000000"


def test_bucket_full_name_does_not_double_append():
    assert cos.bucket_full_name("mybucket-1300000000", "1300000000") == "mybucket-1300000000"


def test_resolve_appid_prefers_param():
    module = SimpleNamespace(params={"appid": 1300000000})
    assert cos.resolve_appid(module) == "1300000000"


def test_get_bucket_tags_parses_tag_set():
    client = FakeCosClient({"b-1": _bucket(tags={"env": "prod"})})
    assert cos.get_bucket_tags(client, "b-1") == {"env": "prod"}


def test_get_bucket_tags_maps_no_such_tag_set_to_empty():
    client = FakeCosClient({"b-1": _bucket()})
    assert cos.get_bucket_tags(client, "b-1") == {}


def test_describe_bucket_returns_none_when_missing():
    client = FakeCosClient()
    assert cos.describe_bucket(client, "b-missing") is None


def test_describe_bucket_collects_attributes():
    client = FakeCosClient({
        "mybucket-1": _bucket(acl="public-read", versioning="Enabled", tags={"env": "prod"}),
    })
    result = cos.describe_bucket(client, "mybucket-1", short_name="mybucket")
    assert result == {
        "name": "mybucket",
        "full_name": "mybucket-1",
        "location": "ap-guangzhou",
        "acl": "public-read",
        "versioning": True,
        "tags": {"env": "prod"},
    }


def test_describe_bucket_versioning_disabled():
    client = FakeCosClient({"b-1": _bucket(versioning="Suspended")})
    assert cos.describe_bucket(client, "b-1")["versioning"] is False


def test_list_buckets_normalizes_entries():
    client = FakeCosClient({"b-1": _bucket(), "b-2": _bucket(location="ap-shanghai")})
    buckets = cos.list_buckets(client, region="ap-guangzhou")
    assert [b["name"] for b in buckets] == ["b-1", "b-2"]
    assert buckets[0]["location"] == "ap-guangzhou"
    assert buckets[0]["creation_date"] == "2026-08-26T00:00:00Z"


def test_list_buckets_empty():
    class EmptyClient(object):
        def list_buckets(self, **kwargs):
            return {"Buckets": None}

    assert cos.list_buckets(EmptyClient()) == []


class FakeCosConfig(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeCosS3Client(object):
    def __init__(self, config):
        self.config = config


class FakeApi3CredentialModule(object):
    class Credential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.token = token


class FakeTempCredentials(object):
    TmpSecretId = "tmp-akid"
    TmpSecretKey = "tmp-secret"
    Token = "tmp-token"


class FakeAssumeRoleResponse(object):
    Credentials = FakeTempCredentials()


COS_PARAMS = {
    "secret_id": "akid-test",
    "secret_key": "secret-test",
    "token": None,
    "region": "ap-guangzhou",
    "timeout": 60,
    "endpoint": None,
    "user_agent": None,
    "role_arn": None,
    "role_session_name": "ansible-tencentcloud",
    "role_session_duration": 7200,
}


def _fake_cos_sdk(monkeypatch):
    """Make cos.py believe both SDKs are present, with fake classes."""
    monkeypatch.setattr(cos, "HAS_COS_SDK", True)
    monkeypatch.setattr(cos, "CosConfig", FakeCosConfig, raising=False)
    monkeypatch.setattr(cos, "CosS3Client", FakeCosS3Client, raising=False)
    monkeypatch.setattr(cos.api3_client, "HAS_TENCENTCLOUD_SDK", True)
    monkeypatch.setattr(
        cos.api3_client, "tc_credential", FakeApi3CredentialModule, raising=False
    )


def test_create_cos_client_with_role_arn_uses_temporary_credentials(monkeypatch):
    _fake_cos_sdk(monkeypatch)
    captured = {}

    def fake_assume_role(module, base_credential):
        captured["base_credential"] = base_credential
        return FakeAssumeRoleResponse()

    monkeypatch.setattr(cos.api3_client, "_assume_role", fake_assume_role)
    params = dict(COS_PARAMS, role_arn="qcs::cam::uin/1:roleName/ops")
    module = SimpleNamespace(params=params)
    s3_client = cos.create_cos_client(module)

    assert captured["base_credential"].secret_id == "akid-test"
    assert s3_client.config.SecretId == "tmp-akid"
    assert s3_client.config.SecretKey == "tmp-secret"
    assert s3_client.config.Token == "tmp-token"
    assert s3_client.config.Region == "ap-guangzhou"


def test_create_cos_client_without_role_arn_keeps_credentials(monkeypatch):
    _fake_cos_sdk(monkeypatch)

    def explode(module, credential):
        raise AssertionError("STS must not be called without role_arn")

    monkeypatch.setattr(cos.api3_client, "_assume_role", explode)
    params = dict(COS_PARAMS, token="session-token")
    module = SimpleNamespace(params=params)
    s3_client = cos.create_cos_client(module)

    assert s3_client.config.SecretId == "akid-test"
    assert s3_client.config.SecretKey == "secret-test"
    assert s3_client.config.Token == "session-token"
