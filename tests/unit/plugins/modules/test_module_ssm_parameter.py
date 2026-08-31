"""Unit tests for the ssm_parameter write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_parameter import (
    _create,
    _delete,
    _restore,
    _update_description,
    _update_value,
    _value_matches,
    find_secret,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeSecretRequest = FakeRequest
    CreateSecretRequest = FakeRequest
    UpdateSecretRequest = FakeRequest
    DeleteSecretRequest = FakeRequest
    GetSecretValueRequest = FakeRequest
    UpdateDescriptionRequest = FakeRequest
    RestoreSecretRequest = FakeRequest
    Tag = FakeRequest


class FakeSecret(object):
    def __init__(self, name, description=None, status="Enabled"):
        self.SecretName = name
        self.Description = description
        self.Status = status
        self.SecretType = 0

    def _serialize(self, allow_none=True):
        return {
            "SecretName": self.SecretName,
            "Description": self.Description,
            "Status": self.Status,
            "SecretType": self.SecretType,
        }


class FakeResponse(object):
    pass


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeSecret(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateSecret(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def UpdateSecret(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteSecret(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def GetSecretValue(self, request):
        self.calls.append(request)
        return self.response

    def UpdateDescription(self, request):
        self.calls.append(request)
        return self.response

    def RestoreSecret(self, request):
        self.calls.append(request)
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound.Secret"


def test_find_secret_returns_metadata():
    client = FakeClient(FakeSecret("prod/db"))
    module = FakeModule()
    secret = find_secret(module, client, FakeModels, "prod/db")
    assert secret["SecretName"] == "prod/db"
    assert len(client.calls) == 1


def test_find_secret_returns_none_on_not_found():
    client = FakeClient(exc=NotFoundError())
    module = FakeModule()
    assert find_secret(module, client, FakeModels, "missing") is None


def test_find_secret_raises_other_errors():
    class OtherError(Exception):
        def get_code(self):
            return "AuthFailure"

    client = FakeClient(exc=OtherError())
    module = FakeModule()
    try:
        find_secret(module, client, FakeModels, "x")
        assert False, "expected exception"
    except OtherError:
        pass


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _create(module, client, FakeModels, {
        "secret_name": "prod/db",
        "secret_string": "s3cr3t",
        "secret_binary": None,
        "description": "db password",
        "secret_type": 0,
        "encrypt_type": 1,
        "kms_key_id": "kms-123",
        "tags": {"env": "prod", "owner": "platform"},
    })
    request = client.calls[-1]
    assert request.SecretName == "prod/db"
    assert request.SecretString == "s3cr3t"
    assert request.Description == "db password"
    assert request.SecretType == 0
    assert request.EncryptType == 1
    assert request.KmsKeyId == "kms-123"
    assert [(tag.TagKey, tag.TagValue) for tag in request.Tags] == [("env", "prod"), ("owner", "platform")]


def test_create_omits_optional_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _create(module, client, FakeModels, {
        "secret_name": "prod/db",
        "secret_string": "s3cr3t",
        "secret_binary": None,
        "description": None,
        "secret_type": 0,
        "encrypt_type": None,
        "kms_key_id": None,
        "tags": {},
    })
    request = client.calls[-1]
    assert request.SecretName == "prod/db"
    assert not hasattr(request, "Description")
    assert not hasattr(request, "EncryptType")
    assert not hasattr(request, "KmsKeyId")


def test_update_value_sends_string():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _update_value(module, client, FakeModels, "prod/db", "new-value", None)
    request = client.calls[-1]
    assert request.SecretName == "prod/db"
    assert request.SecretString == "new-value"
    assert not hasattr(request, "SecretBinary")


def test_update_value_sends_binary():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _update_value(module, client, FakeModels, "prod/db", None, "YmFzZTY0")
    assert client.calls[-1].SecretBinary == "YmFzZTY0"


def test_delete_soft_mode_sets_recovery_window():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _delete(module, client, FakeModels, "prod/db", False, 30)
    request = client.calls[-1]
    assert request.SecretName == "prod/db"
    assert request.RecoveryWindowInDays == 30
    assert not hasattr(request, "DeleteMode")


def test_delete_immediate_mode_zeroes_recovery_window():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _delete(module, client, FakeModels, "prod/db", True, 30)
    request = client.calls[-1]
    assert request.SecretName == "prod/db"
    assert request.RecoveryWindowInDays == 0
    assert not hasattr(request, "DeleteMode")


def test_value_matches_current_string_without_returning_it():
    response = FakeResponse()
    response.SecretString = "same"
    response.SecretBinary = None
    client = FakeClient(response)
    assert _value_matches(FakeModule(), client, FakeModels, "prod/db", "same", None)
    assert client.calls[-1].SecretName == "prod/db"


def test_update_description_uses_dedicated_api():
    client = FakeClient(FakeResponse())
    _update_description(FakeModule(), client, FakeModels, "prod/db", "new description")
    assert client.calls[-1].SecretName == "prod/db"
    assert client.calls[-1].Description == "new description"


def test_restore_uses_restore_secret_api():
    client = FakeClient(FakeResponse())
    _restore(FakeModule(), client, FakeModels, "prod/db")
    assert client.calls[-1].SecretName == "prod/db"
