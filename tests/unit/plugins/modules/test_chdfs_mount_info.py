"""Tests for the CHDFS mount-point reader: chdfs_mount_access_groups_info.

The module reports which access groups a single CHDFS mount point carries.
``build_request`` scopes ``DescribeMountPoints`` to one file system and the
client-side match narrows the answer to one ``mount_point_id``, so the two
facts a caller cares about -- the requested id exists, and which access groups
it binds -- are the whole module.

The request-builder test came first and stays as it was. Everything below
drives ``run_module()`` end to end through the shared harness: the module
builds its own ``ChdfsClient``, so the fake ``tencentcloud.chdfs.v20201112``
service is injected into ``sys.modules`` and the two factories
(``create_credential`` / ``create_client_profile``) are patched on the module.
The real ``sdk_call`` runs, which is what makes the two failure envelopes --
the SDK one and the unexpected one -- the module's own behaviour rather than a
test double's.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import tencentcloud as tc
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_mount_access_groups_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FILE_SYSTEM_ID = "f-4d7a91c3"
MOUNT_POINT_ID = "mp-3f8c1a2b"
REGION = "ap-guangzhou"
ENDPOINT = "chdfs.tencentcloudapi.com"


def test_mount_access_groups_request_sets_file_system_id():
    request = mod.build_request(FakeModels(), "fs-x")
    assert request.FileSystemId == "fs-x"


#: One mount point as ``DescribeMountPoints`` returns it: the real SDK field
#: names (``MountPointId``, ``MountPointName``, ``FileSystemId``, ``Status``,
#: ``CreateTime``, ``AccessGroupIds``) and an access-group list the API is free
#: to return in any order.
MOUNT_POINT = {
    "MountPointId": MOUNT_POINT_ID,
    "MountPointName": "etl-mount",
    "FileSystemId": FILE_SYSTEM_ID,
    "Status": 1,
    "CreateTime": "2026-01-08 11:22:33",
    "AccessGroupIds": ["ag-9", "ag-2"],
}

OTHER_MOUNT_POINT = {
    "MountPointId": "mp-000000ff",
    "MountPointName": "archive-mount",
    "FileSystemId": FILE_SYSTEM_ID,
    "Status": 2,
    "CreateTime": "2026-01-09 08:00:00",
    "AccessGroupIds": ["ag-7"],
}


class FakeChdfsClient(object):
    """CHDFS client answering ``DescribeMountPoints`` with one canned page."""

    def __init__(self, mount_points=None, error=None):
        self.mount_points = mount_points
        self.error = error
        self.requests = []

    def DescribeMountPoints(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            MountPoints=None if self.mount_points is None else [FakeResource(point) for point in self.mount_points],
            RequestId="req-chdfs-1",
        )


def _inject_sdk(monkeypatch, client):
    """Install a fake ``tencentcloud.chdfs.v20201112`` service.

    The module imports the client and the models inside ``run_module`` (the
    lazy-import convention every module follows), so the service has to be
    reachable through ``sys.modules``. The client factory records the
    credential, region and profile it was handed, which is how the tests see
    the endpoint and the argument spec the module passes.
    """
    factory_calls = []

    def factory(credential, region, profile):
        factory_calls.append((credential, region, profile))
        return client

    service = types.ModuleType("tencentcloud.chdfs.v20201112")
    service.models = FakeModels()
    service.chdfs_client = SimpleNamespace(ChdfsClient=factory)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.chdfs", types.ModuleType("tencentcloud.chdfs"))
    monkeypatch.setitem(sys.modules, "tencentcloud.chdfs.v20201112", service)
    return factory_calls


@pytest.fixture
def sdk(monkeypatch):
    """Patch the credential/profile factories the module builds its client with."""
    credential = SimpleNamespace(name="credential")
    profile = SimpleNamespace(name="profile")
    monkeypatch.setattr(mod, "create_credential", lambda module: credential)
    monkeypatch.setattr(mod, "create_client_profile", lambda module, endpoint: profile)
    return credential, profile


def _args(**extra):
    args = {"file_system_id": FILE_SYSTEM_ID, "mount_point_id": MOUNT_POINT_ID, "region": REGION}
    args.update(extra)
    return module_args(**args)


def test_run_module_returns_the_mount_point_and_its_sorted_access_groups(monkeypatch, sdk):
    client = FakeChdfsClient([MOUNT_POINT, OTHER_MOUNT_POINT])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(mod.run_module)

    assert payload["changed"] is False
    assert payload["access_group_ids"] == ["ag-2", "ag-9"]
    assert payload["mount_point"] == MOUNT_POINT
    assert payload["request_id"] == "req-chdfs-1"
    assert payload.keys() == {"changed", "access_group_ids", "mount_point", "request_id"}


def test_run_module_scopes_the_describe_to_the_file_system(monkeypatch, sdk):
    """One ``DescribeMountPoints`` for the file system, through the real client."""
    credential, profile = sdk
    client = FakeChdfsClient([MOUNT_POINT])
    factory_calls = _inject_sdk(monkeypatch, client)
    _args()

    run(mod.run_module)

    assert [request.FileSystemId for request in client.requests] == [FILE_SYSTEM_ID]
    assert factory_calls == [(credential, REGION, profile)]


def test_run_module_selects_the_requested_mount_point(monkeypatch, sdk):
    """A second mount point on the same file system is not the answer."""
    client = FakeChdfsClient([OTHER_MOUNT_POINT, MOUNT_POINT])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(mod.run_module)

    assert payload["mount_point"]["MountPointId"] == MOUNT_POINT_ID
    assert payload["mount_point"]["MountPointName"] == "etl-mount"
    assert payload["access_group_ids"] == ["ag-2", "ag-9"]


def test_run_module_reports_no_access_groups_for_an_unbound_mount_point(monkeypatch, sdk):
    """``AccessGroupIds: null`` in the API means "bound to nothing"."""
    client = FakeChdfsClient([dict(MOUNT_POINT, AccessGroupIds=None)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(mod.run_module)

    assert payload["access_group_ids"] == []
    assert payload["mount_point"]["AccessGroupIds"] is None
    assert payload["changed"] is False


def test_run_module_fails_when_the_mount_point_is_not_found(monkeypatch, sdk):
    client = FakeChdfsClient([OTHER_MOUNT_POINT])
    _inject_sdk(monkeypatch, client)
    _args(mount_point_id="mp-missing")

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "CHDFS mount point was not found"
    assert payload["mount_point_id"] == "mp-missing"


def test_run_module_fails_when_the_file_system_has_no_mount_points(monkeypatch, sdk):
    """``MountPoints: null`` is the same answer as an empty list: not found."""
    client = FakeChdfsClient(None)
    _inject_sdk(monkeypatch, client)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "CHDFS mount point was not found"


def test_run_module_maps_an_sdk_error_to_fail_json(monkeypatch, sdk):
    class FakeSdkException(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-chdfs-err"

    monkeypatch.setattr(tc, "TencentCloudSDKException", FakeSdkException)
    client = FakeChdfsClient(error=FakeSdkException("not allowed to describe mount points"))
    _inject_sdk(monkeypatch, client)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "not allowed to describe mount points"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-chdfs-err"


def test_run_module_maps_an_unexpected_error_to_fail_json(monkeypatch, sdk):
    """A non-SDK exception still fails the task instead of escaping."""
    client = FakeChdfsClient(error=RuntimeError("socket closed"))
    _inject_sdk(monkeypatch, client)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Unexpected Tencent Cloud API error"
    assert payload["error"] == "socket closed"


def test_run_module_requires_the_file_system_id(monkeypatch, sdk):
    _inject_sdk(monkeypatch, FakeChdfsClient([MOUNT_POINT]))
    module_args(mount_point_id=MOUNT_POINT_ID, region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: file_system_id"


def test_run_module_requires_the_mount_point_id(monkeypatch, sdk):
    _inject_sdk(monkeypatch, FakeChdfsClient([MOUNT_POINT]))
    module_args(file_system_id=FILE_SYSTEM_ID, region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: mount_point_id"


def test_run_module_requires_the_chdfs_sdk_package(monkeypatch, sdk):
    """Without the per-product SDK the module names the package to install."""
    monkeypatch.setitem(sys.modules, "tencentcloud.chdfs.v20201112", None)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "The tencentcloud-sdk-python-chdfs package is required."


def test_run_module_reads_in_check_mode(monkeypatch, sdk):
    """A reader can run in check mode: it only ever reads."""
    client = FakeChdfsClient([MOUNT_POINT])
    _inject_sdk(monkeypatch, client)
    _args(_ansible_check_mode=True)

    payload = run(mod.run_module)

    assert payload["access_group_ids"] == ["ag-2", "ag-9"]
    assert payload["changed"] is False
    assert len(client.requests) == 1
