"""Main-path unit tests for the sms_signature module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sms_signature
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SIGN_NAME = "Tencent Cloud"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeSmsClient(object):
    """In-memory stand-in for the SmsClient signature operations."""

    def __init__(self, signs=None):
        self.signs = list(signs or [])
        self.describe_offsets = []
        self.DescribeSmsSignList = MagicMock(side_effect=self._describe)
        self.AddSmsSign = MagicMock(side_effect=self._add)
        self.DeleteSmsSign = MagicMock(side_effect=self._delete)

    def _describe(self, request):
        self.describe_offsets.append(request.Offset or 0)
        start = request.Offset or 0
        end = start + (request.Limit or 100)
        items = [FakeResource(s) for s in self.signs[start:end]]
        return SimpleNamespace(DescribeSignListStatusSet=items)

    def _add(self, request):
        self.signs.append({
            "SignId": 9999,
            "SignName": request.SignName,
            "International": request.International,
            "StatusCode": 1,
        })
        return SimpleNamespace(AddSignStatus=FakeResource({"SignId": 9999}))

    def _delete(self, request):
        self.signs = [s for s in self.signs if s["SignId"] != request.SignId]
        return SimpleNamespace()


def make_sign(sign_id=1110, status=0, name=SIGN_NAME, international=0, review_reply=None):
    data = {
        "SignId": sign_id,
        "SignName": name,
        "International": international,
        "StatusCode": status,
    }
    if review_reply is not None:
        data["ReviewReply"] = review_reply
    return data


@pytest.fixture
def client(monkeypatch):
    fake = FakeSmsClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        sms_signature, "_load_sms",
        lambda: (FakeModels(), SimpleNamespace(SmsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


CREATE_ARGS = dict(
    sign_name=SIGN_NAME,
    sign_type=0,
    document_type=0,
    sign_purpose=0,
    proof_image="aGVsbG8=",
)


def test_absent_noop_when_sign_missing(client):
    module_args(sign_name=SIGN_NAME, state="absent")
    result = run(sms_signature.run_module)
    assert result["changed"] is False
    client.DeleteSmsSign.assert_not_called()


def test_absent_deletes_existing_sign(client):
    client.signs = [make_sign(sign_id=1110, status=0)]
    module_args(sign_name=SIGN_NAME, state="absent")
    result = run(sms_signature.run_module)
    assert result["changed"] is True
    request = client.DeleteSmsSign.call_args[0][0]
    assert request.SignId == 1110


def test_absent_check_mode_does_not_delete(client):
    client.signs = [make_sign(sign_id=1110, status=0)]
    module_args(sign_name=SIGN_NAME, state="absent", _ansible_check_mode=True)
    result = run(sms_signature.run_module)
    assert result["changed"] is True
    client.DeleteSmsSign.assert_not_called()


def test_present_noop_when_active(client):
    client.signs = [make_sign(sign_id=1110, status=0, review_reply="ok")]
    module_args(**CREATE_ARGS)
    result = run(sms_signature.run_module)
    assert result["changed"] is False
    assert result["sign_id"] == 1110
    assert result["status_code"] == 0
    assert result["review_reply"] == "ok"
    client.AddSmsSign.assert_not_called()


def test_present_noop_when_in_review(client):
    client.signs = [make_sign(sign_id=1110, status=1)]
    module_args(**CREATE_ARGS)
    result = run(sms_signature.run_module)
    assert result["changed"] is False
    client.AddSmsSign.assert_not_called()


def test_present_creates_when_absent(client):
    module_args(**CREATE_ARGS)
    result = run(sms_signature.run_module)
    assert result["changed"] is True
    assert result["sign_id"] == 9999
    request = client.AddSmsSign.call_args[0][0]
    assert request.SignName == SIGN_NAME
    assert request.SignType == 0
    assert request.DocumentType == 0
    assert request.SignPurpose == 0
    assert request.ProofImage == "aGVsbG8="
    assert request.International == 0


def test_present_resubmits_rejected_sign(client):
    client.signs = [make_sign(sign_id=1110, status=-1, review_reply="bad proof")]
    module_args(**CREATE_ARGS)
    result = run(sms_signature.run_module)
    assert result["changed"] is True
    client.AddSmsSign.assert_called_once()
    request = client.AddSmsSign.call_args[0][0]
    assert request.SignName == SIGN_NAME


def test_present_check_mode_does_not_create(client):
    module_args(**CREATE_ARGS, _ansible_check_mode=True)
    result = run(sms_signature.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.AddSmsSign.assert_not_called()


def test_present_diff_in_normal_run(client):
    module_args(**CREATE_ARGS, _ansible_diff=True)
    result = run(sms_signature.run_module)
    assert result["changed"] is True
    assert result["diff"]["after"]["SignName"] == SIGN_NAME


def test_international_flag_maps_to_one(client):
    module_args(**dict(CREATE_ARGS, international=True))
    run(sms_signature.run_module)
    request = client.AddSmsSign.call_args[0][0]
    assert request.International == 1
    # the lookup must also filter on the international flag
    assert client.DescribeSmsSignList.call_args[0][0].International == 1


def test_present_missing_create_params_fails(client):
    module_args(sign_name=SIGN_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(sms_signature.run_module)
    assert "sign_type" in exc.value.args[0]["msg"]
    assert "proof_image" in exc.value.args[0]["msg"]
    client.AddSmsSign.assert_not_called()


def test_optional_create_fields_forwarded(client):
    module_args(**dict(CREATE_ARGS, commission_image="Y29tbQ==", qualification_id="1000001", remark="urgent"))
    run(sms_signature.run_module)
    request = client.AddSmsSign.call_args[0][0]
    assert request.CommissionImage == "Y29tbQ=="
    assert request.QualificationId == "1000001"
    assert request.Remark == "urgent"


def test_pagination_scans_beyond_first_page(client):
    client.signs = [make_sign(sign_id=i, status=0, name="other-{0}".format(i)) for i in range(150)]
    client.signs.append(make_sign(sign_id=150, status=0))
    module_args(**CREATE_ARGS)
    result = run(sms_signature.run_module)
    assert result["changed"] is False
    assert result["sign_id"] == 150
    assert client.describe_offsets == [0, 100]


def test_skips_rejected_match_when_usable_exists(client):
    client.signs = [
        make_sign(sign_id=1, status=-1),
        make_sign(sign_id=2, status=0),
    ]
    module_args(**CREATE_ARGS)
    result = run(sms_signature.run_module)
    assert result["changed"] is False
    assert result["sign_id"] == 2


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(**CREATE_ARGS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(sms_signature.run_module)
    assert exc.value.args[0]["failed"] is True
