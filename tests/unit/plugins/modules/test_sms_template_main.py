"""Main-path unit tests for the sms_template module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sms_template
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TEMPLATE_NAME = "Login verification code"
TEMPLATE_CONTENT = "Your verification code is {1}."


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
    """In-memory stand-in for the SmsClient template operations."""

    def __init__(self, templates=None):
        self.templates = list(templates or [])
        self.DescribeSmsTemplateList = MagicMock(side_effect=self._describe)
        self.AddSmsTemplate = MagicMock(side_effect=self._add)
        self.DeleteSmsTemplate = MagicMock(side_effect=self._delete)

    def _describe(self, request):
        start = request.Offset or 0
        end = start + (request.Limit or 100)
        items = [FakeResource(t) for t in self.templates[start:end]]
        return SimpleNamespace(DescribeTemplateStatusSet=items)

    def _add(self, request):
        self.templates.append({
            "TemplateId": 2222,
            "TemplateName": request.TemplateName,
            "International": request.International,
            "StatusCode": 1,
        })
        return SimpleNamespace(AddTemplateStatus=FakeResource({"TemplateId": 2222}))

    def _delete(self, request):
        self.templates = [t for t in self.templates if t["TemplateId"] != request.TemplateId]
        return SimpleNamespace()


def make_template(template_id=1110, status=0, name=TEMPLATE_NAME, international=0):
    return {
        "TemplateId": template_id,
        "TemplateName": name,
        "International": international,
        "StatusCode": status,
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeSmsClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        sms_template, "_load_sms",
        lambda: (FakeModels(), SimpleNamespace(SmsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


CREATE_ARGS = dict(
    template_name=TEMPLATE_NAME,
    sms_type=0,
    template_content=TEMPLATE_CONTENT,
)


def test_absent_noop_when_template_missing(client):
    module_args(template_name=TEMPLATE_NAME, state="absent")
    result = run(sms_template.run_module)
    assert result["changed"] is False
    client.DeleteSmsTemplate.assert_not_called()


def test_absent_deletes_existing_template(client):
    client.templates = [make_template(template_id=1110, status=0)]
    module_args(template_name=TEMPLATE_NAME, state="absent")
    result = run(sms_template.run_module)
    assert result["changed"] is True
    request = client.DeleteSmsTemplate.call_args[0][0]
    assert request.TemplateId == 1110


def test_absent_check_mode_does_not_delete(client):
    client.templates = [make_template(template_id=1110, status=0)]
    module_args(template_name=TEMPLATE_NAME, state="absent", _ansible_check_mode=True)
    result = run(sms_template.run_module)
    assert result["changed"] is True
    client.DeleteSmsTemplate.assert_not_called()


def test_present_noop_when_active(client):
    client.templates = [make_template(template_id=1110, status=0)]
    module_args(**CREATE_ARGS)
    result = run(sms_template.run_module)
    assert result["changed"] is False
    assert result["template_id"] == 1110
    assert result["status_code"] == 0
    client.AddSmsTemplate.assert_not_called()


def test_present_noop_when_approved_pending(client):
    client.templates = [make_template(template_id=1110, status=2)]
    module_args(**CREATE_ARGS)
    result = run(sms_template.run_module)
    assert result["changed"] is False
    client.AddSmsTemplate.assert_not_called()


def test_present_creates_when_absent(client):
    module_args(**CREATE_ARGS)
    result = run(sms_template.run_module)
    assert result["changed"] is True
    assert result["template_id"] == 2222
    request = client.AddSmsTemplate.call_args[0][0]
    assert request.TemplateName == TEMPLATE_NAME
    assert request.TemplateContent == TEMPLATE_CONTENT
    assert request.SmsType == 0
    assert request.International == 0


def test_present_resubmits_rejected_template(client):
    client.templates = [make_template(template_id=1110, status=-1)]
    module_args(**CREATE_ARGS)
    result = run(sms_template.run_module)
    assert result["changed"] is True
    client.AddSmsTemplate.assert_called_once()


def test_present_check_mode_does_not_create(client):
    module_args(**CREATE_ARGS, _ansible_check_mode=True)
    result = run(sms_template.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.AddSmsTemplate.assert_not_called()


def test_international_flag_maps_to_one(client):
    module_args(**dict(CREATE_ARGS, international=True))
    run(sms_template.run_module)
    request = client.AddSmsTemplate.call_args[0][0]
    assert request.International == 1
    assert client.DescribeSmsTemplateList.call_args[0][0].International == 1


def test_present_missing_create_params_fails(client):
    module_args(template_name=TEMPLATE_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(sms_template.run_module)
    assert "sms_type" in exc.value.args[0]["msg"]
    assert "template_content" in exc.value.args[0]["msg"]
    client.AddSmsTemplate.assert_not_called()


def test_remark_forwarded_when_provided(client):
    module_args(**dict(CREATE_ARGS, remark="expires in 5 minutes"))
    run(sms_template.run_module)
    request = client.AddSmsTemplate.call_args[0][0]
    assert request.Remark == "expires in 5 minutes"


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(**CREATE_ARGS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(sms_template.run_module)
    assert exc.value.args[0]["failed"] is True
