"""Deep harness tests for the cam_role_info module.

Covers build_request's page-based pagination, run_module pagination through
DescribeRoleList, the client-side role_id/role_name filters, empty-page
termination and the sdk_call failure contract -- driven through the shared
harness rather than a private double.

The module builds its own SDK client, so the tests still inject a fake
``tencentcloud.cam.v20190116`` service and patch the two factories. Driving
the real ``AnsibleModule`` is what makes the payload observable, and the
fixture already serialises ``RoleId``/``RoleName``, so the captured payload is
what ``add_return_samples.py`` writes into the module's RETURN sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cam_role_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeModels:
    DescribeRoleListRequest = FakeRequest


def test_build_request_uses_page_based_pagination():
    request = cam_role_info.build_request(FakeModels, 3, 100)
    assert request.Page == 3
    assert request.Rp == 100


class FakeItem:
    def __init__(self, role_id, role_name):
        self.RoleId = role_id
        self.RoleName = role_name

    def _serialize(self, allow_none=True):
        return {"RoleId": self.RoleId, "RoleName": self.RoleName}


class FakeListResponse:
    def __init__(self, items, total_num):
        self.List = items
        self.TotalNum = total_num


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeRoleList(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class SdkError(Exception):
    """The SDK exception shape the shared read wrapper catches.

    ``read_sdk_call`` resolves ``TencentCloudSDKException`` through its own
    module global, so ``_point_wrapper_at_sdk_error`` binds that name here and
    the fake client can raise something the real wrapper classifies.
    """

    def __init__(self, code, message, request_id):
        super(SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _point_wrapper_at_sdk_error(monkeypatch):
    from ansible_collections.susunola.tencentcloud.plugins.module_utils import tencentcloud as wrapper

    monkeypatch.setattr(wrapper, "TencentCloudSDKException", SdkError)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.cam.v20190116")
    service.models = FakeModels
    service.cam_client = types.SimpleNamespace(CamClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cam",
                        types.ModuleType("tencentcloud.cam"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cam.v20190116", service)


@pytest.fixture
def sdk(monkeypatch):
    """Patch the credential/client factories the module builds its client with."""
    monkeypatch.setattr(cam_role_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_role_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    params = {"region": "ap-guangzhou", "page_size": 2}
    params.update(extra)
    module_args(**params)


def test_run_module_paginates_until_total_num_reached(monkeypatch, sdk):
    client = FakeClient([
        FakeListResponse([FakeItem("A1", "role-a"), FakeItem("A2", "role-b")], 3),
        FakeListResponse([FakeItem("A3", "role-c")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(cam_role_info.run_module)

    assert payload["changed"] is False
    assert [item["RoleName"] for item in payload["roles"]] == [
        "role-a", "role-b", "role-c"]
    assert payload["total_count"] == 3
    assert [request.Page for request in client.requests] == [1, 2]


def test_run_module_applies_role_id_and_name_filters(monkeypatch, sdk):
    client = FakeClient([
        FakeListResponse([FakeItem("A1", "role-a"), FakeItem("A1", "role-other"),
                          FakeItem("A9", "role-a")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args(role_id="A1", role_name="role-a", page_size=10)

    payload = run(cam_role_info.run_module)

    assert payload["roles"] == [{"RoleId": "A1", "RoleName": "role-a"}]
    assert payload["total_count"] == 1


def test_run_module_stops_on_empty_page(monkeypatch, sdk):
    client = FakeClient([FakeListResponse([], 0)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(cam_role_info.run_module)

    assert payload["roles"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch, sdk):
    """The shared wrapper's failure contract, exercised rather than restated.

    The read helper is no longer replaced: the client raises the SDK error and
    the real ``read_sdk_call`` classifies it, so the payload below is the one
    the shared code produces. The double that used to stand in for it pinned a
    hand-written copy of the contract, which could not notice the helper
    changing -- and this module now reaches the API through that helper.
    """
    class FailingClient:
        def DescribeRoleList(self, request):
            raise SdkError("UnauthorizedOperation", "api exploded", "req-err")

    _inject_sdk(monkeypatch, FailingClient())
    _point_wrapper_at_sdk_error(monkeypatch)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(cam_role_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
    # The bucket the shared wrapper derives from the code.
    assert payload["error_class"] == "unauthorized"
