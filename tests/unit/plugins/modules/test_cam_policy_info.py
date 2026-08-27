from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.cam_policy_info import (
    SCOPE_MAP,
    build_request,
)


class FakeRequest:
    pass


class FakeModels:
    ListPoliciesRequest = FakeRequest


def test_build_request_maps_scope_and_pagination():
    request = build_request(FakeModels, "local", None, 2, 100)
    assert request.Scope == "Local"
    assert request.Page == 2
    assert request.Rp == 100
    assert not hasattr(request, "Keyword") or request.Keyword is None


def test_build_request_passes_keyword():
    request = build_request(FakeModels, "qcs", "app-read-only", 1, 50)
    assert request.Scope == "QCS"
    assert request.Keyword == "app-read-only"


def test_scope_map_covers_all_choices():
    assert SCOPE_MAP == {"all": "All", "local": "Local", "qcs": "QCS"}
