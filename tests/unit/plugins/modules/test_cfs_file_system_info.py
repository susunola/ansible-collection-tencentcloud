from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cfs_file_system_info


class FakeRequest:
    pass


class FakeModels:
    DescribeCfsFileSystemsRequest = FakeRequest


def test_build_request_maps_file_system_id_and_int_pagination():
    request = cfs_file_system_info.build_request(FakeModels, 'cfs-123', 20, 100)
    assert request.FileSystemId == "cfs-123"
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_omits_file_system_id_when_none():
    request = cfs_file_system_info.build_request(FakeModels, None, 20, 100)
    assert not hasattr(request, "FileSystemId")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.FileSystems = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeCfsFileSystems(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class ModuleExit(Exception):
    pass


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        raise AssertionError("fail_json called: %r" % (kwargs,))


def _run(monkeypatch, client, **params):
    service = types.ModuleType("tencentcloud.cfs.v20190719")
    service.models = FakeModels
    service.cfs_client = types.SimpleNamespace(CfsClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cfs", types.ModuleType("tencentcloud.cfs"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cfs.v20190719", service)
    fake = FakeModule(params)
    monkeypatch.setattr(cfs_file_system_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cfs_file_system_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cfs_file_system_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cfs_file_system_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", file_system_id=None, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["file_systems"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
