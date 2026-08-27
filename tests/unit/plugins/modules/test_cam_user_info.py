from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.cam_user_info import (
    build_request,
    matches,
)


class FakeRequest:
    pass


class FakeModels:
    ListUsersRequest = FakeRequest


class FakeUser:
    def __init__(self, name):
        self.Name = name


def test_build_request_takes_no_parameters():
    request = build_request(FakeModels)
    assert isinstance(request, FakeRequest)


def test_matches_without_filters():
    assert matches(FakeUser("deploy-bot")) is True


def test_matches_exact_name():
    assert matches(FakeUser("deploy-bot"), name="deploy-bot") is True
    assert matches(FakeUser("deploy-bot"), name="deploy") is False


def test_matches_name_keyword_substring():
    assert matches(FakeUser("deploy-bot"), name_keyword="bot") is True
    assert matches(FakeUser("deploy-bot"), name_keyword="ci") is False


def test_matches_combines_name_and_keyword():
    assert matches(FakeUser("deploy-bot"), name="deploy-bot", name_keyword="bot") is True
    assert matches(FakeUser("deploy-bot"), name="deploy-bot", name_keyword="ci") is False


def test_matches_tolerates_none_name():
    assert matches(FakeUser(None), name_keyword="bot") is False
