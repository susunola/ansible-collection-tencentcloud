"""Unit tests for the ssm_parameter write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_parameter import (
    _create,
    _delete,
    _update_value,
    find_secret,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeSecretRequest = FakeRequest
    CreateSecretRequest = FakeRequest
    UpdateSecretRequest = FakeRequest
    DeleteSecretRequest = FakeRequest


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
    })
    request = client.calls[-1]
    assert request.SecretName == "prod/db"
    assert request.SecretString == "s3cr3t"
    assert request.Description == "db password"
    assert request.SecretType == 0
    assert request.EncryptType == 1
    assert request.KmsKeyId == "kms-123"


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
    assert request.DeleteMode == "recover"
    assert request.RecoveryWindowInDays == 30


def test_delete_immediate_mode():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _delete(module, client, FakeModels, "prod/db", True, 30)
    request = client.calls[-1]
    assert request.DeleteMode == "immediate"
    assert not hasattr(request, "RecoveryWindowInDays")
