"""Unit tests for the scf_function write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
import base64
import os
import tempfile
import zipfile

from ansible_collections.susunola.tencentcloud.plugins.modules.scf_function import (
    _build_code,
    _build_environment,
    _build_vpc_config,
    _create,
    _delete,
    _update_code,
    _update_config,
    find_function,
    _read_zip_b64,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    GetFunctionRequest = FakeRequest
    CreateFunctionRequest = FakeRequest
    UpdateFunctionCodeRequest = FakeRequest
    UpdateFunctionConfigurationRequest = FakeRequest
    DeleteFunctionRequest = FakeRequest
    Code = FakeRequest
    Environment = FakeRequest
    Variable = FakeRequest
    VpcConfig = FakeRequest


class FakeFunction(object):
    def __init__(self, name, runtime="Python3.10", handler="index.main_handler"):
        self.FunctionName = name
        self.Runtime = runtime
        self.Handler = handler
        self.MemorySize = 128
        self.Timeout = 3
        self.Description = None
        self.CodeSize = 0
        self.Status = "Active"

    def _serialize(self, allow_none=True):
        return {
            "FunctionName": self.FunctionName,
            "Runtime": self.Runtime,
            "Handler": self.Handler,
            "MemorySize": self.MemorySize,
            "Timeout": self.Timeout,
            "Description": self.Description,
            "CodeSize": self.CodeSize,
            "Status": self.Status,
        }


class FakeResponse(object):
    pass


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def GetFunction(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateFunction(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def UpdateFunctionCode(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def UpdateFunctionConfiguration(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteFunction(self, request):
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
        return "ResourceNotFound.FunctionName"


def make_zip():
    handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    handle.close()
    with zipfile.ZipFile(handle.name, "w") as archive:
        archive.writestr("index.py", "def main_handler(event, context):\n    return 'ok'\n")
    return handle.name


def test_find_function_returns_metadata():
    client = FakeClient(FakeFunction("hello"))
    module = FakeModule()
    fn = find_function(module, client, FakeModels, "hello", "default")
    assert fn["FunctionName"] == "hello"
    assert len(client.calls) == 1
    assert client.calls[-1].Namespace == "default"


def test_find_function_returns_none_on_not_found():
    client = FakeClient(exc=NotFoundError())
    module = FakeModule()
    assert find_function(module, client, FakeModels, "missing", "default") is None


def test_read_zip_b64_returns_payload_and_digest():
    path = make_zip()
    try:
        payload, digest = _read_zip_b64(path)
        raw = base64.b64decode(payload)
        assert raw.startswith(b"PK")
        assert len(digest) == 64
    finally:
        os.unlink(path)


def test_build_code_from_zip():
    path = make_zip()
    try:
        params = {
            "zip_file": path,
            "cos_bucket_name": None,
            "cos_object_name": None,
            "cos_bucket_region": None,
            "region": "ap-guangzhou",
        }
        code = _build_code(FakeModels, params)
        assert code.ZipFile.startswith("UEsD")
        assert not hasattr(code, "CosBucketName")
    finally:
        os.unlink(path)


def test_build_code_from_cos():
    params = {
        "zip_file": None,
        "cos_bucket_name": "my-bucket",
        "cos_object_name": "fn.zip",
        "cos_bucket_region": "ap-shanghai",
        "region": "ap-guangzhou",
    }
    code = _build_code(FakeModels, params)
    assert code.CosBucketName == "my-bucket"
    assert code.CosObjectName == "fn.zip"
    assert code.CosBucketRegion == "ap-shanghai"
    assert not hasattr(code, "ZipFile")


def test_build_environment_sorts_variables():
    env = _build_environment(FakeModels, {"b": "2", "a": "1"})
    assert [v.Key for v in env.Variables] == ["a", "b"]
    assert env.Variables[0].Value == "1"


def test_build_environment_none_when_empty():
    assert _build_environment(FakeModels, {}) is None


def test_build_vpc_config():
    config = _build_vpc_config(FakeModels, "vpc-1", "subnet-2")
    assert config.VpcId == "vpc-1"
    assert config.SubnetId == "subnet-2"


def test_build_vpc_config_none_when_empty():
    assert _build_vpc_config(FakeModels, None, None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    params = {
        "function_name": "hello",
        "namespace": "default",
        "runtime": "Python3.10",
        "handler": "index.main_handler",
        "description": "demo",
        "memory_size": 256,
        "execution_timeout": 10,
        "zip_file": None,
        "cos_bucket_name": "b",
        "cos_object_name": "f.zip",
        "cos_bucket_region": "ap-guangzhou",
        "environment": {"K": "V"},
        "role": "SCF_QcsRole",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-2",
    }
    _create(module, client, FakeModels, params)
    request = client.calls[-1]
    assert request.FunctionName == "hello"
    assert request.Runtime == "Python3.10"
    assert request.Handler == "index.main_handler"
    assert request.MemorySize == 256
    assert request.Timeout == 10
    assert request.Code.CosBucketName == "b"
    assert request.Environment.Variables[0].Key == "K"
    assert request.Role == "SCF_QcsRole"
    assert request.VpcConfig.VpcId == "vpc-1"


def test_update_code_publishes_and_sends_zip():
    path = make_zip()
    try:
        client = FakeClient(FakeResponse())
        module = FakeModule()
        params = {
            "zip_file": path,
            "cos_bucket_name": None,
            "cos_object_name": None,
            "cos_bucket_region": None,
            "region": "ap-guangzhou",
            "handler": "index.main_handler",
        }
        _update_code(module, client, FakeModels, "hello", "default", params)
        request = client.calls[-1]
        assert request.FunctionName == "hello"
        assert request.Namespace == "default"
        assert request.Publish == "TRUE"
        assert request.ZipFile.startswith("UEsD")
    finally:
        os.unlink(path)


def test_update_config_sends_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    params = {
        "function_name": "hello",
        "namespace": "default",
        "description": "new desc",
        "memory_size": 512,
        "execution_timeout": 30,
        "environment": {},
        "role": None,
        "vpc_id": None,
        "subnet_id": None,
    }
    _update_config(module, client, FakeModels, "hello", "default", params)
    request = client.calls[-1]
    assert request.FunctionName == "hello"
    assert request.Description == "new desc"
    assert request.MemorySize == 512
    assert request.Timeout == 30
    assert not hasattr(request, "Role")
    assert not hasattr(request, "VpcConfig")


def test_delete_sends_name_and_namespace():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _delete(module, client, FakeModels, "hello", "default")
    request = client.calls[-1]
    assert request.FunctionName == "hello"
    assert request.Namespace == "default"
