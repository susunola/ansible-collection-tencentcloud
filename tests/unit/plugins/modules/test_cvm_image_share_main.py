"""Main-path unit tests for the cvm_image_share module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_image_share
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

IMAGE_ID = "img-12345678"
ACCT_A = "100000000001"
ACCT_B = "100000000002"
ACCT_C = "100000000003"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeCvmClient(object):
    """In-memory stand-in for the CvmClient image-share operations."""

    def __init__(self, shared=None):
        self.shared = set(shared or [])
        self.ModifyImageSharePermission = MagicMock(side_effect=self._modify)

    def DescribeImageSharePermission(self, request):
        items = [FakeResource({"AccountId": account}) for account in sorted(self.shared)]
        return SimpleNamespace(SharePermissionSet=items)

    def _modify(self, request):
        accounts = list(request.AccountIds)
        if request.Permission == "SHARE":
            self.shared.update(accounts)
        elif request.Permission == "CANCEL":
            self.shared.difference_update(accounts)
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeCvmClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cvm_image_share, "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_present_shares_new_accounts(client):
    client.shared = {ACCT_A}
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[ACCT_A, ACCT_B],
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == sorted([ACCT_A, ACCT_B])
    client.ModifyImageSharePermission.assert_called_once()
    request = client.ModifyImageSharePermission.call_args[0][0]
    assert request.ImageId == IMAGE_ID
    assert request.AccountIds == [ACCT_B]
    assert request.Permission == "SHARE"


def test_present_unchanged(client):
    client.shared = {ACCT_A}
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[ACCT_A],
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is False
    assert result["shared_accounts"] == [ACCT_A]
    client.ModifyImageSharePermission.assert_not_called()


def test_present_shares_multiple_in_one_call(client):
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[ACCT_A, ACCT_B, ACCT_C],
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is True
    request = client.ModifyImageSharePermission.call_args[0][0]
    assert request.AccountIds == sorted([ACCT_A, ACCT_B, ACCT_C])


def test_present_deduplicates_and_sorts(client):
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[ACCT_B, ACCT_A, ACCT_B],
    )
    result = run(cvm_image_share.run_module)
    request = client.ModifyImageSharePermission.call_args[0][0]
    assert request.AccountIds == [ACCT_A, ACCT_B]
    assert result["shared_accounts"] == [ACCT_A, ACCT_B]


def test_absent_cancels_shared_accounts(client):
    client.shared = {ACCT_A, ACCT_B}
    module_args(
        state="absent", image_id=IMAGE_ID,
        account_ids=[ACCT_B],
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == [ACCT_A]
    request = client.ModifyImageSharePermission.call_args[0][0]
    assert request.AccountIds == [ACCT_B]
    assert request.Permission == "CANCEL"


def test_absent_ignores_unshared_accounts(client):
    client.shared = {ACCT_A, ACCT_B, ACCT_C}
    module_args(
        state="absent", image_id=IMAGE_ID,
        account_ids=[ACCT_B, ACCT_C],
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is True
    request = client.ModifyImageSharePermission.call_args[0][0]
    assert request.AccountIds == [ACCT_B, ACCT_C]
    assert result["shared_accounts"] == [ACCT_A]


def test_absent_unchanged(client):
    client.shared = {ACCT_A}
    module_args(
        state="absent", image_id=IMAGE_ID,
        account_ids=[ACCT_B],
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is False
    assert result["shared_accounts"] == [ACCT_A]
    client.ModifyImageSharePermission.assert_not_called()


def test_check_mode_reports_without_writes(client):
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[ACCT_B],
        _ansible_check_mode=True,
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == [ACCT_B]
    assert "Would share" in result["msg"]
    client.ModifyImageSharePermission.assert_not_called()


def test_check_mode_absent(client):
    client.shared = {ACCT_A, ACCT_B}
    module_args(
        state="absent", image_id=IMAGE_ID,
        account_ids=[ACCT_A],
        _ansible_check_mode=True,
    )
    result = run(cvm_image_share.run_module)
    assert result["changed"] is True
    assert "Would cancel" in result["msg"]
    client.ModifyImageSharePermission.assert_not_called()


def test_empty_account_ids_fails(client):
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[],
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cvm_image_share.run_module)
    assert "must not be empty" in excinfo.value.args[0]["msg"]


def test_sdk_error_fails(client, monkeypatch):
    def boom(module, client, models, image_id):
        raise FakeSdkError("InvalidImageId.NotFound")

    monkeypatch.setattr(cvm_image_share, "find_shared_accounts", boom)
    module_args(
        state="present", image_id=IMAGE_ID,
        account_ids=[ACCT_A],
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cvm_image_share.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "InvalidImageId.NotFound"
    assert payload["request_id"] == "req-fake"
