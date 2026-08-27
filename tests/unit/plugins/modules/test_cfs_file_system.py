"""Unit tests for the cfs_file_system write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cfs_file_system import (
    _create,
    _delete,
    _update_name,
    _update_size_limit,
    build_describe_request,
    find_file_system,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeCfsFileSystemsRequest = FakeRequest
    CreateCfsFileSystemRequest = FakeRequest
    UpdateCfsFileSystemNameRequest = FakeRequest
    UpdateCfsFileSystemSizeLimitRequest = FakeRequest
    DeleteCfsFileSystemRequest = FakeRequest


class FakeFileSystem(object):
    def __init__(self, fs_id, name, capacity=10, size_limit=None):
        self.FileSystemId = fs_id
        self.Name = name
        self.Capacity = capacity
        self.SizeLimit = size_limit

    def _serialize(self, allow_none=True):
        return {
            "FileSystemId": self.FileSystemId,
            "Name": self.Name,
            "Capacity": self.Capacity,
            "SizeLimit": self.SizeLimit,
        }


class FakeResponse(object):
    def __init__(self, file_systems, total=0):
        self.FileSystems = file_systems
        self.TotalCount = total


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeCfsFileSystems(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateCfsFileSystem(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def UpdateCfsFileSystemName(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def UpdateCfsFileSystemSizeLimit(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteCfsFileSystem(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "cfs-123", None)
    assert request.FileSystemId == "cfs-123"
    assert request.Offset == 0
    assert request.Limit == 100


def test_build_describe_request_without_id():
    request = build_describe_request(FakeModels, None, "app-share")
    assert not hasattr(request, "FileSystemId") or request.FileSystemId is None


def test_find_file_system_by_id():
    client = FakeClient(FakeResponse([FakeFileSystem("cfs-1", "other")], total=1))
    module = FakeModule()
    found = find_file_system(module, client, FakeModels, "cfs-1", None)
    assert found["FileSystemId"] == "cfs-1"
    assert len(client.calls) == 1


def test_find_file_system_by_name_paginates():
    class PaginatedClient(object):
        def __init__(self):
            self.calls = []
            # Offset snapshots: find_file_system reuses one request object, so
            # reading request.Offset afterwards yields the final page offset.
            self.offsets = []

        def DescribeCfsFileSystems(self, request):
            self.calls.append(request)
            self.offsets.append(request.Offset)
            if request.Offset == 0:
                return FakeResponse([FakeFileSystem("cfs-1", "other")], total=2)
            return FakeResponse([FakeFileSystem("cfs-2", "app-share")], total=2)

    client = PaginatedClient()
    module = FakeModule()
    found = find_file_system(module, client, FakeModels, None, "app-share")
    assert found["FileSystemId"] == "cfs-2"
    assert client.offsets == [0, 1]


def test_find_file_system_returns_none_when_absent():
    client = FakeClient(FakeResponse([], total=0))
    module = FakeModule()
    assert find_file_system(module, client, FakeModels, "cfs-9", None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "zone": "ap-guangzhou-3",
        "protocol": "NFS",
        "storage_type": "SD",
        "capacity": 100,
        "name": "app-share",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "pgroup_id": "pgroup-1",
    })
    request = client.calls[-1]
    assert request.Zone == "ap-guangzhou-3"
    assert request.Protocol == "NFS"
    assert request.StorageType == "SD"
    assert request.Capacity == 100
    assert request.FsName == "app-share"
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.PGroupId == "pgroup-1"


def test_create_omits_unset_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "zone": "ap-guangzhou-3",
        "protocol": "NFS",
        "storage_type": "SD",
        "capacity": 10,
        "name": None,
        "vpc_id": None,
        "subnet_id": None,
        "pgroup_id": None,
    })
    request = client.calls[-1]
    assert not hasattr(request, "FsName")
    assert not hasattr(request, "VpcId")
    assert not hasattr(request, "SubnetId")
    assert not hasattr(request, "PGroupId")


def test_update_name():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update_name(module, client, FakeModels, "cfs-1", "app-share-v2")
    request = client.calls[-1]
    assert request.FileSystemId == "cfs-1"
    assert request.FsName == "app-share-v2"


def test_update_size_limit():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update_size_limit(module, client, FakeModels, "cfs-1", 200)
    request = client.calls[-1]
    assert request.FileSystemId == "cfs-1"
    assert request.FsLimit == 200


def test_delete_sends_file_system_id():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "cfs-1")
    request = client.calls[-1]
    assert request.FileSystemId == "cfs-1"
