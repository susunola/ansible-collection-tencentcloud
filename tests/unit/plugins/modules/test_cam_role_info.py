from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.tencentcloud.cloud.plugins.modules.cam_role_info import build_request


class FakeRequest:
    pass


class FakeModels:
    DescribeRoleListRequest = FakeRequest


def test_build_request_uses_page_based_pagination():
    request = build_request(FakeModels, 3, 100)
    assert request.Page == 3
    assert request.Rp == 100
